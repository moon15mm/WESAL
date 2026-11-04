"""Reports & analytics for each role, with CSV / XLSX / PDF export, and the order document PDF."""
from __future__ import annotations

import html
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db, system_context
from app.core.deps import BusinessCtx, Principal, RepCtx, current_principal, rep_ctx, retailer_ctx, supplier_ctx
from app.core.errors import NotFound
from app.core.i18n import localized, normalize_locale, t
from app.core.utils import money, utcnow
from app.models.business import Business, City
from app.models.commissions import Commission
from app.models.crm import Customer, CustomerAcquisition, Visit
from app.models.enums import CommissionStatus, OrderStatus as S, VisitStatus
from app.models.orders import Order, OrderApproval, OrderItem, ReturnRequest
from app.models.reps import Representative
from app.modules.orders.service import SALES_STATUSES
from app.modules.reports import export

router = APIRouter(tags=["reports"])

Fmt = Literal["json", "csv", "xlsx", "pdf"]


def _range(date_from: datetime | None, date_to: datetime | None) -> tuple[datetime, datetime]:
    end = date_to or utcnow()
    start = date_from or (end - timedelta(days=30))
    return start, end


def _series(db: Session, where, start, end, value=Order.total, bucket: str = "day") -> list[dict]:
    b = func.date_trunc(bucket, Order.created_at)
    rows = db.execute(select(b, func.count(), func.coalesce(func.sum(value), 0)).where(where, Order.created_at.between(start, end))
                      .group_by(b).order_by(b)).all()
    return [{"period": p.date().isoformat(), "orders": n, "value": money(v)} for p, n, v in rows]


def _top_products(db: Session, where, start, end, locale, limit=10) -> list[dict]:
    rows = db.execute(select(OrderItem.product_id, func.max(OrderItem.name_ar), func.max(OrderItem.name_en),
                             func.sum(OrderItem.quantity * OrderItem.pieces_per_unit), func.sum(OrderItem.line_total))
                      .join(Order, Order.id == OrderItem.order_id).where(where, Order.created_at.between(start, end))
                      .group_by(OrderItem.product_id).order_by(func.sum(OrderItem.line_total).desc()).limit(limit)).all()
    return [{"product_id": str(p), "name": ar if locale == "ar" else en, "pieces": int(q or 0), "value": money(v)}
            for p, ar, en, q, v in rows]


def _respond(fmt: Fmt, data: dict, title: str, locale: str, sections: list[dict]):
    if fmt == "json":
        return data
    if fmt == "pdf":
        content = export.report_pdf(title, locale, sections, subtitle=f"{data['period']['from']} → {data['period']['to']}")
        return Response(content, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="wesal-report.pdf"'})
    main = sections[0]
    if fmt == "csv":
        return Response(export.to_csv(main["columns"], main["rows"]), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="wesal-report.csv"'})
    from openpyxl import Workbook  # noqa: F401  (ensures dependency present)

    content = _xlsx_multi(title, sections, locale)
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="wesal-report.xlsx"'})


def _xlsx_multi(title: str, sections: list[dict], locale: str) -> bytes:
    import io

    from openpyxl import load_workbook

    first = export.to_xlsx(sections[0]["heading"], sections[0]["columns"], sections[0]["rows"], locale)
    wb = load_workbook(io.BytesIO(first))
    for s in sections[1:]:
        tmp = load_workbook(io.BytesIO(export.to_xlsx(s["heading"], s["columns"], s["rows"], locale))).active
        ws = wb.create_sheet(s["heading"][:31])
        ws.sheet_view.rightToLeft = tmp.sheet_view.rightToLeft
        for row in tmp.iter_rows(values_only=True):
            ws.append(row)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def L(key: str, locale: str) -> str:
    return t(f"reports.{key}", locale)


# ------------------------------------------------------------------ retailer
@router.get("/reports/retailer")
def retailer_report(date_from: datetime | None = None, date_to: datetime | None = None, format: Fmt = "json",
                    db: Session = Depends(get_db), ctx: BusinessCtx = Depends(retailer_ctx("retailer.reports.view"))):
    start, end = _range(date_from, date_to)
    loc = ctx.principal.locale
    base = Order.retailer_id == ctx.business_id
    if ctx.member.branch_id:
        base = and_(base, Order.branch_id == ctx.member.branch_id)
    sales = and_(base, Order.status.in_(SALES_STATUSES | {S.completed}))
    total, n = db.execute(select(func.coalesce(func.sum(Order.total), 0), func.count()).where(sales, Order.created_at.between(start, end))).one()
    completed = db.scalar(select(func.count()).select_from(Order).where(base, Order.status == S.completed, Order.created_at.between(start, end)))
    late = db.scalar(select(func.count()).select_from(Order).where(
        base, Order.expected_delivery_date.isnot(None), Order.created_at.between(start, end),
        case((Order.delivered_at.isnot(None), func.date(Order.delivered_at) > Order.expected_delivery_date),
             else_=and_(Order.status.in_([S.approved, S.preparing, S.ready, S.out_for_delivery]),
                        Order.expected_delivery_date < func.current_date())))) or 0
    by_supplier = db.execute(select(Business, func.count(), func.coalesce(func.sum(Order.total), 0)).join(
        Business, Business.id == Order.supplier_id).where(sales, Order.created_at.between(start, end))
        .group_by(Business.id).order_by(func.sum(Order.total).desc()).limit(20)).all()
    pending = db.scalar(select(func.count()).select_from(Order).where(
        base, Order.status.in_([S.pending_retailer_approval, S.quoted, S.awaiting_retailer_approval]))) or 0
    data = {
        "period": {"from": start.date().isoformat(), "to": end.date().isoformat()},
        "kpis": {"purchases": money(total), "orders": n, "completed": completed or 0, "late": late,
                 "avg_order": money(total / n) if n else Decimal("0"), "pending_approvals": pending},
        "series": _series(db, sales, start, end),
        "suppliers": [{"supplier_id": str(b.id), "name": b.display_name(loc), "orders": c, "value": money(v)} for b, c, v in by_supplier],
        "top_products": _top_products(db, sales, start, end, loc),
    }
    sections = [
        {"heading": L("by_supplier", loc), "columns": [("name", L("supplier", loc)), ("orders", L("orders", loc)), ("value", L("value", loc))],
         "rows": data["suppliers"], "numeric": ["orders", "value"]},
        {"heading": L("top_products", loc), "columns": [("name", L("product", loc)), ("pieces", L("pieces", loc)), ("value", L("value", loc))],
         "rows": data["top_products"], "numeric": ["pieces", "value"]},
        {"heading": L("over_time", loc), "columns": [("period", L("period", loc)), ("orders", L("orders", loc)), ("value", L("value", loc))],
         "rows": data["series"], "numeric": ["orders", "value"]},
    ]
    return _respond(format, data, L("retailer_title", loc), loc, sections)


# ------------------------------------------------------------------ representative
@router.get("/reports/rep")
def rep_report(date_from: datetime | None = None, date_to: datetime | None = None, format: Fmt = "json",
               db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    start, end = _range(date_from, date_to)
    loc = ctx.principal.locale
    rid = ctx.rep.id
    base = Order.representative_id == rid
    created = db.scalar(select(func.count()).select_from(Order).where(base, Order.created_at.between(start, end))) or 0
    approved = db.scalar(select(func.count()).select_from(Order).where(
        base, Order.created_at.between(start, end), Order.status.in_(SALES_STATUSES | {S.completed, S.new, S.supplier_review, S.quoted}))) or 0
    sales_where = and_(base, Order.status.in_(SALES_STATUSES | {S.completed}))
    sales = db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(sales_where, Order.created_at.between(start, end))) or 0
    visits = db.scalar(select(func.count()).select_from(Visit).where(Visit.representative_id == rid, Visit.status == VisitStatus.completed,
                                                                     Visit.ended_at.between(start, end))) or 0
    customers = db.scalar(select(func.count()).select_from(Customer).where(Customer.owner_representative_id == rid)) or 0
    comm = db.execute(select(Commission.status, func.coalesce(func.sum(Commission.amount), 0)).where(
        Commission.representative_id == rid, Commission.created_at.between(start, end)).group_by(Commission.status)).all()
    by_city = db.execute(select(City, func.count(), func.coalesce(func.sum(Order.total), 0)).join(City, City.id == Order.city_id)
                         .where(sales_where, Order.created_at.between(start, end)).group_by(City.id)).all()
    by_supplier = db.execute(select(Business, func.count(), func.coalesce(func.sum(Order.total), 0)).join(
        Business, Business.id == Order.supplier_id).where(sales_where, Order.created_at.between(start, end)).group_by(Business.id)).all()
    data = {
        "period": {"from": start.date().isoformat(), "to": end.date().isoformat()},
        "kpis": {"visits": visits, "customers": customers, "orders_created": created, "orders_approved": approved,
                 "sales": money(sales), "conversion_rate": round(approved / created * 100, 1) if created else 0,
                 "commissions": {s.value: money(v) for s, v in comm},
                 "commissions_total": money(sum((v for s, v in comm if s != CommissionStatus.cancelled), Decimal("0")))},
        "series": _series(db, sales_where, start, end),
        "by_city": [{"city": localized(c.name, loc), "orders": n, "value": money(v)} for c, n, v in by_city],
        "by_supplier": [{"name": b.display_name(loc), "orders": n, "value": money(v)} for b, n, v in by_supplier],
    }
    sections = [
        {"heading": L("by_supplier", loc), "columns": [("name", L("supplier", loc)), ("orders", L("orders", loc)), ("value", L("value", loc))],
         "rows": data["by_supplier"], "numeric": ["orders", "value"]},
        {"heading": L("by_city", loc), "columns": [("city", L("city", loc)), ("orders", L("orders", loc)), ("value", L("value", loc))],
         "rows": data["by_city"], "numeric": ["orders", "value"]},
        {"heading": L("over_time", loc), "columns": [("period", L("period", loc)), ("orders", L("orders", loc)), ("value", L("value", loc))],
         "rows": data["series"], "numeric": ["orders", "value"]},
    ]
    return _respond(format, data, L("rep_title", loc), loc, sections)


# ------------------------------------------------------------------ supplier
@router.get("/reports/supplier")
def supplier_report(date_from: datetime | None = None, date_to: datetime | None = None, format: Fmt = "json",
                    db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx("supplier.reports.view"))):
    start, end = _range(date_from, date_to)
    loc = ctx.principal.locale
    sid = ctx.business_id
    base = Order.supplier_id == sid
    sales_where = and_(base, Order.status.in_(SALES_STATUSES | {S.completed}))
    in_range = Order.created_at.between(start, end)
    sales, n = db.execute(select(func.coalesce(func.sum(Order.total), 0), func.count()).where(sales_where, in_range)).one()
    statuses = dict(db.execute(select(Order.status, func.count()).where(base, in_range,
                                                                        Order.status.notin_([S.draft, S.pending_retailer_approval]))
                               .group_by(Order.status)).all())
    active_customers = db.scalar(select(func.count(func.distinct(Order.retailer_id))).where(sales_where, in_range)) or 0
    new_customers = db.scalar(select(func.count()).select_from(CustomerAcquisition).where(
        CustomerAcquisition.supplier_id == sid, CustomerAcquisition.acquired_at.between(start, end))) or 0
    reps = db.execute(select(Representative, func.count(Order.id), func.coalesce(func.sum(Order.total), 0))
                      .join(Order, Order.representative_id == Representative.id).where(sales_where, in_range)
                      .group_by(Representative.id).order_by(func.sum(Order.total).desc())).all()
    rep_comm = dict(db.execute(select(Commission.representative_id, func.coalesce(func.sum(Commission.amount), 0)).where(
        Commission.supplier_id == sid, Commission.created_at.between(start, end), Commission.status != CommissionStatus.cancelled)
        .group_by(Commission.representative_id)).all())
    returns_n, returns_v = db.execute(select(func.count(), func.coalesce(func.sum(ReturnRequest.total_value), 0)).where(
        ReturnRequest.supplier_id == sid, ReturnRequest.created_at.between(start, end))).one()
    geo = db.execute(select(City, func.count(), func.coalesce(func.sum(Order.total), 0)).join(City, City.id == Order.city_id)
                     .where(sales_where, in_range).group_by(City.id).order_by(func.sum(Order.total).desc())).all()
    channel = dict(db.execute(select(Order.channel, func.coalesce(func.sum(Order.total), 0)).where(sales_where, in_range)
                              .group_by(Order.channel)).all())
    comm_total = db.scalar(select(func.coalesce(func.sum(Commission.amount), 0)).where(
        Commission.supplier_id == sid, Commission.created_at.between(start, end), Commission.status != CommissionStatus.cancelled)) or 0
    data = {
        "period": {"from": start.date().isoformat(), "to": end.date().isoformat()},
        "kpis": {"sales": money(sales), "orders": n, "avg_order": money(sales / n) if n else Decimal("0"),
                 "active_customers": active_customers, "new_customers": new_customers, "returns": returns_n,
                 "returns_value": money(returns_v), "commissions": money(comm_total),
                 "new_orders": statuses.get(S.new, 0) + statuses.get(S.supplier_review, 0),
                 "in_preparation": statuses.get(S.preparing, 0) + statuses.get(S.approved, 0) + statuses.get(S.ready, 0)},
        "statuses": {s.value: c for s, c in statuses.items()},
        "channels": {c.value: money(v) for c, v in channel.items()},
        "series": _series(db, sales_where, start, end),
        "top_products": _top_products(db, sales_where, start, end, loc),
        "representatives": [{"representative_id": str(r.id), "name": r.display_name, "orders": c, "value": money(v),
                             "commission": money(rep_comm.get(r.id, 0))} for r, c, v in reps],
        "geography": [{"city": localized(c.name, loc), "orders": k, "value": money(v)} for c, k, v in geo],
    }
    sections = [
        {"heading": L("top_products", loc), "columns": [("name", L("product", loc)), ("pieces", L("pieces", loc)), ("value", L("value", loc))],
         "rows": data["top_products"], "numeric": ["pieces", "value"]},
        {"heading": L("representatives", loc), "columns": [("name", L("representative", loc)), ("orders", L("orders", loc)),
                                                            ("value", L("value", loc)), ("commission", L("commission", loc))],
         "rows": data["representatives"], "numeric": ["orders", "value", "commission"]},
        {"heading": L("by_city", loc), "columns": [("city", L("city", loc)), ("orders", L("orders", loc)), ("value", L("value", loc))],
         "rows": data["geography"], "numeric": ["orders", "value"]},
        {"heading": L("over_time", loc), "columns": [("period", L("period", loc)), ("orders", L("orders", loc)), ("value", L("value", loc))],
         "rows": data["series"], "numeric": ["orders", "value"]},
    ]
    return _respond(format, data, L("supplier_title", loc), loc, sections)


# ------------------------------------------------------------------ order document (PDF)
@router.get("/orders/{oid}/document.pdf")
def order_document(oid: uuid.UUID, request: Request, locale: str | None = Query(default=None), db: Session = Depends(get_db),
                   principal: Principal = Depends(current_principal)):
    with system_context(db):
        o = db.get(Order, oid)
    bids = set(principal.business_ids())
    rep_id = principal.rep.id if principal.rep else None
    allowed = o is not None and (o.retailer_id in bids or (o.supplier_id in bids and o.status not in (S.draft, S.pending_retailer_approval))
                                 or (rep_id and o.representative_id == rep_id) or bool(principal.platform_perms))
    if not allowed:
        raise NotFound()
    loc = normalize_locale(locale or principal.user.document_locale or principal.locale)
    with system_context(db):
        approval = db.scalar(select(OrderApproval).where(OrderApproval.order_id == o.id, OrderApproval.decision == "approved")
                             .order_by(OrderApproval.decided_at.desc()).limit(1))
        content = export.to_pdf_html(render_order_html(o, loc, approval))
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{o.number}.pdf"', "Cache-Control": "private, no-store"})


def render_order_html(o: Order, loc: str, approval: OrderApproval | None) -> str:
    e = html.escape

    def party(title_key: str, b: Business, extra: str = "") -> str:
        lines = [b.legal_name, b.trade_name_ar if loc == "ar" else (b.trade_name_en or b.trade_name_ar)]
        if b.cr_number:
            lines.append(f"{t('pdf.cr', loc)}: <span class='ltr'>{e(b.cr_number)}</span>")
        if b.vat_number:
            lines.append(f"{t('pdf.vat_number', loc)}: <span class='ltr'>{e(b.vat_number)}</span>")
        if b.phone:
            lines.append(f"<span class='ltr'>{e(b.phone)}</span>")
        return f"<div class='card'><b>{e(t(title_key, loc))}</b>{'<br>'.join(l if '<span' in l else e(l) for l in lines)}{extra}</div>"

    branch = ""
    if o.branch:
        branch = f"<br>{e(t('pdf.branch', loc))}: {e(o.branch.name)} {e(o.branch.district or '')} {e(o.branch.address_line or '')}"
    cols = [("name", t("pdf.item", loc)), ("unit", t("pdf.unit", loc)), ("quantity", t("pdf.qty", loc)),
            ("unit_price", t("pdf.unit_price", loc)), ("discount", t("pdf.discount", loc)), ("line_total", t("pdf.line_total", loc))]
    rows = [{"name": (i.name_ar if loc == "ar" else i.name_en) + (f" ({i.sku})" if i.sku else ""),
             "unit": t(f"units.{i.unit.value}", loc), "quantity": i.quantity, "unit_price": i.unit_price,
             "discount": i.discount, "line_total": i.line_total} for i in o.items]
    totals = [(t("pdf.subtotal", loc), o.subtotal), (t("pdf.discount", loc), o.discount_total),
              (t("pdf.delivery_fee", loc), o.delivery_fee),
              (f"{t('pdf.vat', loc)} ({int(o.vat_rate * 100)}%)", o.vat_total)]
    totals_html = "".join(f"<tr><td>{e(k)}</td><td class='num'>{e(format(v, 'f'))} {e(o.currency)}</td></tr>" for k, v in totals)
    totals_html += f"<tr class='grand'><td>{e(t('pdf.total', loc))}</td><td class='num'>{e(format(o.total, 'f'))} {e(o.currency)}</td></tr>"
    appr = ""
    if approval:
        appr = (f"<h2>{e(t('pdf.approval', loc))}</h2><div class='meta'>{e(t('pdf.approved_at', loc))}: "
                f"<span class='ltr'>{e(approval.decided_at.strftime('%Y-%m-%d %H:%M') if approval.decided_at else '')}</span> · "
                f"{e(t('pdf.version', loc))} {approval.version} · {e(t('pdf.method', loc))}: {e(t('pdf.methods.' + (approval.method.value if approval.method else 'session'), loc))}"
                f"<br>{e(t('pdf.fingerprint', loc))}: <span class='ltr'>{e(approval.snapshot_hash[:32])}</span></div>")
    rep = f"<div class='meta'>{e(t('pdf.representative', loc))}: {e(o.representative.display_name)}</div>" if o.representative else ""
    body = (f"<h1>{e(t('pdf.order_title', loc))} <span class='ltr'>{e(o.number)}</span></h1>"
            f"<div class='meta'>{e(t('pdf.date', loc))}: <span class='ltr'>{o.created_at.strftime('%Y-%m-%d')}</span> · "
            f"{e(t('pdf.status', loc))}: {e(t('order_status.' + o.status.value, loc))}</div>{rep}"
            f"<div class='grid' style='margin-top:10px'>{party('pdf.supplier', o.supplier)}{party('pdf.buyer', o.retailer, branch)}</div>"
            f"<h2>{e(t('pdf.items', loc))}</h2>{export.table_html(cols, rows, {'quantity', 'unit_price', 'discount', 'line_total'})}"
            f"<table class='totals'>{totals_html}</table>{appr}"
            f"<div class='note'>{e(t('pdf.disclaimer', loc))}</div>")
    return export.html_document(f"{t('pdf.order_title', loc)} {o.number}", loc, body)
