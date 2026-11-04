"""WESAL assistant endpoints. All features are scoped to the caller's own data and can be
disabled globally (AI_ENABLED / platform setting `ai_enabled`) without affecting the platform."""
from __future__ import annotations

import time
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import BusinessCtx, Principal, RepCtx, current_principal, rep_ctx, retailer_ctx, supplier_ctx
from app.core.errors import AppError, Forbidden, IntegrationUnavailable
from app.core.utils import money, utcnow
from app.models.enums import OrderStatus as S
from app.models.orders import Order
from app.models.system import AIInteraction, PlatformSetting
from app.modules.ai import local
from app.modules.catalog.router import _market_offers_stmt

router = APIRouter(prefix="/ai", tags=["ai"])


def ai_enabled(db: Session = Depends(get_db)) -> None:
    row = db.get(PlatformSetting, "ai_enabled")
    if not settings.ai_enabled or settings.ai_provider == "none" or (row is not None and row.value is False):
        raise AppError("ai_disabled", status_code=503)


def _log(db: Session, principal: Principal, feature: str, provider: str, inp: str, out: str, started: float, ok=True,
         business_id=None) -> None:
    db.add(AIInteraction(user_id=principal.id, business_id=business_id, feature=feature, provider=provider,
                         input_summary=inp[:500], output_summary=out[:500], latency_ms=int((time.time() - started) * 1000),
                         success=ok))
    db.commit()


@router.get("/status")
def status(db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    row = db.get(PlatformSetting, "ai_enabled")
    enabled = settings.ai_enabled and settings.ai_provider != "none" and (row is None or row.value is not False)
    return {"enabled": enabled, "provider": settings.ai_provider,
            "llm_available": settings.ai_provider == "anthropic" and bool(settings.anthropic_api_key),
            "features": ["parse_order", "smart_search", "alternatives", "reorder_forecast", "rep_opportunities",
                         "rep_performance", "coverage_gaps", "supplier_summary", "ask"]}


class ParseIn(BaseModel):
    text: str = Field(min_length=2, max_length=4000)
    supplier_id: uuid.UUID | None = None


@router.post("/parse-order", dependencies=[Depends(ai_enabled)])
def parse_order(data: ParseIn, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.create"))):
    ratelimit.hit(f"ai:{ctx.user.id}", 60, 3600)
    started = time.time()
    stmt = _market_offers_stmt()
    if data.supplier_id:
        from app.models.catalog import SupplierProduct

        stmt = stmt.where(SupplierProduct.supplier_id == data.supplier_id)
    result = local.parse_order_text(db, data.text, stmt, ctx.principal.locale)
    _log(db, ctx.principal, "parse_order", "local", data.text, f"{len(result['lines'])} lines", started, business_id=ctx.business_id)
    return result


@router.post("/rep/parse-order", dependencies=[Depends(ai_enabled)])
def rep_parse_order(data: ParseIn, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    from app.models.catalog import SupplierProduct
    from app.models.enums import AuthorizationStatus
    from app.models.reps import Authorization
    from app.modules.authorizations.service import is_effective

    ratelimit.hit(f"ai:{ctx.user.id}", 60, 3600)
    started = time.time()
    allowed = [a.supplier_id for a in db.scalars(select(Authorization).where(
        Authorization.representative_id == ctx.rep.id, Authorization.status == AuthorizationStatus.active)) if is_effective(a)]
    if data.supplier_id and data.supplier_id not in allowed:
        raise Forbidden("authorization_missing")
    stmt = _market_offers_stmt().where(SupplierProduct.supplier_id.in_([data.supplier_id] if data.supplier_id else allowed or [uuid.uuid4()]))
    result = local.parse_order_text(db, data.text, stmt, ctx.principal.locale)
    _log(db, ctx.principal, "parse_order", "local", data.text, f"{len(result['lines'])} lines", started)
    return result


@router.get("/search", dependencies=[Depends(ai_enabled)])
def smart_search(q: str, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    cands = local.offer_candidates(db, q[:200], _market_offers_stmt(), limit=20)
    seen, items = set(), []
    for sp, score in cands:
        if sp.product_id in seen:
            continue
        seen.add(sp.product_id)
        items.append({"product_id": str(sp.product_id), "name": sp.product.name_ar if principal.locale == "ar" else sp.product.name_en,
                      "score": round(score, 2), "package_size": sp.product.package_size})
    return {"items": items, "sources": ["catalog:active_offers"], "method": "trigram similarity with Arabic normalization"}


@router.get("/alternatives/{product_id}", dependencies=[Depends(ai_enabled)])
def alternatives(product_id: uuid.UUID, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    return local.alternatives(db, product_id, _market_offers_stmt(), principal.locale)


@router.get("/reorder-forecast", dependencies=[Depends(ai_enabled)])
def reorder(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.view"))):
    return local.reorder_forecast(db, ctx.business_id, ctx.principal.locale)


@router.get("/rep/opportunities", dependencies=[Depends(ai_enabled)])
def rep_opps(db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    return local.rep_opportunities(db, ctx.rep.id, ctx.principal.locale)


@router.get("/rep/performance", dependencies=[Depends(ai_enabled)])
def rep_perf(days: int = 30, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    return local.rep_performance(db, ctx.rep.id, max(7, min(days, 365)))


@router.get("/supplier/coverage-gaps", dependencies=[Depends(ai_enabled)])
def gaps(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx("supplier.reports.view"))):
    return local.coverage_gaps(db, ctx.business_id, ctx.principal.locale)


@router.get("/supplier/summary", dependencies=[Depends(ai_enabled)])
def summary(request: Request, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx("supplier.reports.view"))):
    from app.core.i18n import t
    from app.modules.reports.router import supplier_report

    report = supplier_report(None, None, "json", db, ctx)
    out = local.supplier_summary(report, ctx.principal.locale)
    out["text"] = [t(f"ai.summary.{b['code']}", ctx.principal.locale, **b["params"]) for b in out["bullets"]]
    return out


# ------------------------------------------------------------------ natural-language Q&A
class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)


def _tools_for(principal: Principal, db: Session, request: Request):
    """Return (tool definitions, executor) limited to the caller's own data."""
    from app.integrations.ai_anthropic import tool

    defs, handlers = [], {}
    retailer = next((m for m in principal.memberships if m.business.type.value == "retailer"), None)
    supplier = next((m for m in principal.memberships if m.business.type.value == "supplier"), None)

    def order_stats(where):
        since = utcnow() - timedelta(days=30)
        n, total = db.execute(select(func.count(), func.coalesce(func.sum(Order.total), 0)).where(where, Order.created_at >= since)).one()
        by_status = {s.value: c for s, c in db.execute(select(Order.status, func.count()).where(where).group_by(Order.status))}
        return {"last_30_days_orders": n, "last_30_days_value_sar": str(money(total)), "orders_by_status": by_status}

    defs.append(tool("search_products", "Search the marketplace catalog (names, sizes). Returns products only, no prices.",
                     {"query": {"type": "string"}}, ["query"]))
    handlers["search_products"] = lambda a: smart_search(a["query"], db, principal)
    if retailer:
        rid = retailer.business_id
        defs.append(tool("my_store_orders_summary", "Order counts and value for the user's store (last 30 days and by status)."))
        handlers["my_store_orders_summary"] = lambda a: order_stats(Order.retailer_id == rid)
        defs.append(tool("my_reorder_forecast", "Products the store is likely to need soon, based on its purchase history."))
        handlers["my_reorder_forecast"] = lambda a: local.reorder_forecast(db, rid, principal.locale)
    if supplier:
        sid = supplier.business_id
        defs.append(tool("my_company_orders_summary", "Order counts and value for the user's supplier company."))
        handlers["my_company_orders_summary"] = lambda a: order_stats(
            (Order.supplier_id == sid) & Order.status.notin_([S.draft, S.pending_retailer_approval]))
        defs.append(tool("coverage_gaps", "Cities with many stores but little supplier coverage."))
        handlers["coverage_gaps"] = lambda a: local.coverage_gaps(db, sid, principal.locale)
    if principal.rep:
        rep_id = principal.rep.id
        defs.append(tool("my_performance", "The representative's sales, visits and conversion vs the previous period."))
        handlers["my_performance"] = lambda a: local.rep_performance(db, rep_id)
        defs.append(tool("my_opportunities", "Prioritized customers and new stores for the representative."))
        handlers["my_opportunities"] = lambda a: local.rep_opportunities(db, rep_id, principal.locale)

    def execute(name: str, args: dict) -> dict:
        if name not in handlers:
            raise ValueError("unknown tool")
        return handlers[name](args)

    return defs, execute


LOCAL_INTENTS = [
    (("pending", "انتظار", "معلق", "approval", "موافق"), "pending"),
    (("sales", "مبيعات", "مشتريات", "purchases", "spend"), "sales"),
    (("reorder", "اعاده", "إعادة", "طلب", "need", "يخلص"), "reorder"),
    (("performance", "اداء", "أداء", "conversion"), "performance"),
]


@router.post("/ask", dependencies=[Depends(ai_enabled)])
def ask(data: AskIn, request: Request, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    ratelimit.hit(f"ai-ask:{principal.id}", 30, 3600)
    started = time.time()
    defs, execute = _tools_for(principal, db, request)
    if settings.ai_provider == "anthropic":
        from app.integrations.ai_anthropic import ClaudeAssistant

        try:
            res = ClaudeAssistant().ask(data.question, principal.locale, defs, execute)
            _log(db, principal, "ask", "anthropic", data.question, res.get("answer") or "", started)
            return {**res, "provider": "anthropic", "sources": res.get("tools_used", [])}
        except IntegrationUnavailable as exc:
            _log(db, principal, "ask", "anthropic", data.question, exc.code, started, ok=False)
            # fall through to the local engine so the feature degrades gracefully
    q = data.question.lower()
    intent = next((name for words, name in LOCAL_INTENTS if any(w in q for w in words)), None)
    names = [d["name"] for d in defs]
    result, tool_used = None, None
    if intent == "pending" or intent == "sales":
        tool_used = next((n for n in names if n.endswith("orders_summary")), None)
    elif intent == "reorder":
        tool_used = "my_reorder_forecast" if "my_reorder_forecast" in names else None
    elif intent == "performance":
        tool_used = "my_performance" if "my_performance" in names else None
    if tool_used:
        result = execute(tool_used, {})
    _log(db, principal, "ask", "local", data.question, tool_used or "no_answer", started)
    return {"answer": None, "data": result, "intent": intent, "provider": "local", "sources": [tool_used] if tool_used else [],
            "refused": False, "available_tools": names}
