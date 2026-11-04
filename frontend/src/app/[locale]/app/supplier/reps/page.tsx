"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Star, UserPlus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Pagination, Tabs } from "@/components/ui/data";
import { Badge, Card, EmptyState, PageHeader, SkeletonRows, StatusBadge } from "@/components/ui/layout";
import { Modal } from "@/components/ui/overlay";
import { Button, Field, Input, Select } from "@/components/ui/primitives";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useCategories, useCities } from "@/lib/hooks";
import { useApiQuery, useList } from "@/lib/list";
import { useApiAction } from "@/lib/useApiForm";

type Rep = { id: string; display_name: string; kind: string; headline: string | null; experience_years: number; availability: string; rating_avg: number; rating_count: number;
  areas: { city: { name: string } | null }[]; categories: { name: string }[]; active_customers: number; companies_count: number; phone_masked: string | null;
  relation?: string; relation_status?: string; phone?: string; email?: string | null; latest_authorization?: { id: string; status: string; number: string } | null; sales_total?: string };

function RepCard({ r, mine }: { r: Rep; mine?: boolean }) {
  const t = useTranslations("reps");
  const f = useFormat();
  return (
    <Card className="flex flex-col">
      <div className="flex items-start gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-teal-500 to-navy-600 font-bold text-white">{r.display_name[0]}</span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-navy-700">{r.display_name}</p>
          <p className="truncate text-xs text-muted">{r.headline || t(`kinds.${r.kind}`)}</p>
        </div>
        {r.rating_count > 0 && <span className="flex items-center gap-1 text-xs"><Star className="h-3.5 w-3.5 fill-warning text-warning" />{r.rating_avg}</span>}
      </div>
      <div className="mt-3 flex flex-wrap gap-1">{r.areas.slice(0, 3).map((a, i) => <Badge key={i}>{a.city?.name}</Badge>)}{r.categories.slice(0, 2).map((c, i) => <Badge key={`c${i}`} tone="teal">{c.name}</Badge>)}</div>
      <p className="mt-3 text-xs text-muted">{t("experience_n", { n: r.experience_years })} · {t("customers_n", { n: r.active_customers })} · {t(`availability.${r.availability}`)}</p>
      {mine ? (
        <div className="mt-3 space-y-1 text-sm">
          <p className="ltr text-muted">{r.phone}</p>
          <p>{t("sales")}: <span className="tabular font-semibold">{f.money(r.sales_total)}</span></p>
          <div className="flex items-center gap-2"><Badge tone={r.relation === "employee" ? "navy" : "teal"}>{t(`relations.${r.relation}`)}</Badge>{r.latest_authorization && <Link href={`/app/supplier/authorizations/${r.latest_authorization.id}`}><StatusBadge status={r.latest_authorization.status} /></Link>}</div>
        </div>
      ) : (
        <Link href={`/app/supplier/authorizations/new?rep=${r.id}&name=${encodeURIComponent(r.display_name)}`} className="mt-4 inline-flex h-9 items-center justify-center rounded-md bg-navy-700 px-3 text-sm font-semibold text-white">{t("offer_authorization")}</Link>
      )}
    </Card>
  );
}

export default function SupplierReps() {
  const t = useTranslations("reps");
  const qc = useQueryClient();
  const cities = useCities();
  const cats = useCategories();
  const [tab, setTab] = useState<"mine" | "directory">("mine");
  const [city, setCity] = useState("");
  const [cat, setCat] = useState("");
  const [minExp, setMinExp] = useState("");
  const mine = useApiQuery<Rep[]>(["sup-reps"], "/supplier/reps");
  const dir = useList<Rep>(tab === "directory" ? "/market/representatives" : null, { city_id: city, category_id: cat, min_experience: minExp }, 12);
  const [adding, setAdding] = useState(false);
  const [v, setV] = useState({ full_name: "", phone: "", email: "", employee_code: "" });
  const { loading, run } = useApiAction();
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("subtitle")} actions={<Button icon={<UserPlus className="h-4 w-4" />} onClick={() => setAdding(true)}>{t("add_company_rep")}</Button>} />
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs value={tab} onChange={setTab} items={[{ value: "mine", label: t("my_reps"), count: mine.data?.length }, { value: "directory", label: t("directory") }]} />
        {tab === "directory" && (
          <div className="flex flex-wrap gap-2">
            <Select value={city} onChange={(e) => { setCity(e.target.value); dir.reset(); }} className="w-40"><option value="">{t("any_city")}</option>{cities.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>
            <Select value={cat} onChange={(e) => { setCat(e.target.value); dir.reset(); }} className="w-44"><option value="">{t("any_category")}</option>{cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>
            <Select value={minExp} onChange={(e) => { setMinExp(e.target.value); dir.reset(); }} className="w-36"><option value="">{t("any_experience")}</option>{[1, 3, 5, 10].map((n) => <option key={n} value={n}>{t("experience_min", { n })}</option>)}</Select>
          </div>
        )}
      </div>
      {tab === "mine" ? (mine.isLoading ? <SkeletonRows /> : mine.data?.length ? <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{mine.data.map((r) => <RepCard key={r.id} r={r} mine />)}</div> : <Card><EmptyState title={t("no_reps")} description={t("no_reps_hint")} /></Card>)
        : dir.isLoading ? <SkeletonRows /> : dir.data?.items.length ? <><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{dir.data.items.map((r) => <RepCard key={r.id} r={r} />)}</div><Card padded={false} className="mt-4"><Pagination page={dir.page} pageSize={dir.pageSize} total={dir.data.total} onPage={dir.setPage} /></Card></> : <Card><EmptyState title={t("no_results")} /></Card>}
      <p className="mt-4 text-xs text-muted">{t("privacy_note")}</p>
      <Modal open={adding} onOpenChange={setAdding} title={t("add_company_rep")} description={t("add_company_rep_hint")}
        footer={<><Button variant="outline" onClick={() => setAdding(false)}>{t("cancel")}</Button><Button loading={loading} disabled={!v.full_name || !v.phone} onClick={async () => {
          if (await run(() => api("/supplier/reps/company", { body: { ...v, email: v.email || null, employee_code: v.employee_code || null } }), { success: t("added") })) { setAdding(false); qc.invalidateQueries({ queryKey: ["sup-reps"] }); }
        }}>{t("add")}</Button></>}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("full_name")} required>{(id) => <Input id={id} value={v.full_name} onChange={(e) => setV({ ...v, full_name: e.target.value })} />}</Field>
          <Field label={t("phone")} required>{(id) => <Input id={id} dir="ltr" value={v.phone} onChange={(e) => setV({ ...v, phone: e.target.value })} />}</Field>
          <Field label={t("email")}>{(id) => <Input id={id} dir="ltr" type="email" value={v.email} onChange={(e) => setV({ ...v, email: e.target.value })} />}</Field>
          <Field label={t("employee_code")}>{(id) => <Input id={id} dir="ltr" value={v.employee_code} onChange={(e) => setV({ ...v, employee_code: e.target.value })} />}</Field>
        </div>
      </Modal>
    </>
  );
}
