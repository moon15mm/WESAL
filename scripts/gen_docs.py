# Run from backend/:  .venv/bin/python ../scripts/gen_docs.py
"""Generate docs/DATABASE_TABLES.md (schema reference) and docs/API_ENDPOINTS.md + docs/openapi.json from code."""
import json, pathlib, collections, sys
sys.path.insert(0, ".")
import os
os.environ.setdefault("LOG_LEVEL", "WARNING")
from app.core.db import Base
import app.models  # noqa
from app.main import app

DOCS = pathlib.Path("../docs")
mods = collections.OrderedDict()
for t in Base.metadata.sorted_tables:
    pass
by_module = collections.defaultdict(list)
for mapper in Base.registry.mappers:
    cls = mapper.class_
    by_module[cls.__module__.split(".")[-1]].append(cls.__table__)
seen = set()
out = ["# Database schema reference (generated)", "",
       "Generated from the SQLAlchemy models (`backend/app/models`). Column types are PostgreSQL types.",
       "RLS = row-level security policy enforced for the runtime role `wesal_app`.", ""]
from sqlalchemy import inspect as _i
rls = set()
mig = pathlib.Path("alembic/versions").glob("*security_rls.py")
src = "".join(p.read_text() for p in mig)
import re
for m in re.finditer(r'^\s*"([a-z_]+)":\s*[\(\[{"]', src, re.M):
    rls.add(m.group(1))
for module in ["identity", "business", "catalog", "reps", "crm", "orders", "commissions", "system"]:
    tables = sorted(by_module.get(module, []), key=lambda t: t.name)
    out += [f"## {module}", ""]
    for t in tables:
        if t.name in seen: continue
        seen.add(t.name)
        out += [f"### `{t.name}`" + ("  · RLS" if t.name in rls else ""), "", "| column | type | null | notes |", "|---|---|---|---|"]
        for c in t.columns:
            notes = []
            if c.primary_key: notes.append("PK")
            for fk in c.foreign_keys: notes.append(f"→ {fk.target_fullname}")
            if c.unique: notes.append("unique")
            if c.index: notes.append("indexed")
            try: typ = str(c.type.compile(dialect=__import__("sqlalchemy.dialects.postgresql", fromlist=["dialect"]).dialect()))
            except Exception: typ = str(c.type)
            out.append(f"| {c.name} | {typ} | {'yes' if c.nullable else 'no'} | {', '.join(notes)} |")
        for con in t.constraints:
            if con.__class__.__name__ == "UniqueConstraint" and len(con.columns) > 1:
                out.append(f"\nUnique: ({', '.join(col.name for col in con.columns)})")
        out.append("")
(DOCS / "DATABASE_TABLES.md").write_text("\n".join(out), encoding="utf-8")
print("tables:", len(seen), "rls:", len(rls))

spec = app.openapi()
(DOCS / "openapi.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
groups = collections.defaultdict(list)
for path, ops in spec["paths"].items():
    for method, op in ops.items():
        tag = (op.get("tags") or ["other"])[0]
        groups[tag].append((path, method.upper(), op.get("summary", "")))
lines = ["# API endpoint index (generated)", "", f"{sum(len(v) for v in groups.values())} operations. Full schema: [`openapi.json`](openapi.json) (OpenAPI 3).", ""]
for tag in sorted(groups):
    lines += [f"## {tag}", "", "| method | path | summary |", "|---|---|---|"]
    for path, m, s in sorted(groups[tag]):
        lines.append(f"| {m} | `{path}` | {s} |")
    lines.append("")
(DOCS / "API_ENDPOINTS.md").write_text("\n".join(lines), encoding="utf-8")
print("operations:", sum(len(v) for v in groups.values()))
