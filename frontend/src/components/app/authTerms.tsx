"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button, Checkbox, Field, Input, Select, Textarea } from "@/components/ui/primitives";
import { useCategories, useCities } from "@/lib/hooks";
import { useApiQuery } from "@/lib/list";

export type Terms = { type: string; agreement_id: string; all_products: boolean; all_areas: boolean; category_ids: number[]; city_ids: number[]; start_date: string; end_date: string; terms: string };
type Agreement = { id: string; name: string; rules: { basis: string; rate: string }[] };

export function defaultTerms(): Terms {
  return { type: "full_sales", agreement_id: "", all_products: true, all_areas: false, category_ids: [], city_ids: [], start_date: new Date().toISOString().slice(0, 10), end_date: "", terms: "" };
}

export function termsBody(v: Terms) {
  return { type: v.type, agreement_id: v.agreement_id || null, all_products: v.all_products, all_areas: v.all_areas,
    products: v.all_products ? [] : v.category_ids.map((category_id) => ({ category_id })), areas: v.all_areas ? [] : v.city_ids.map((city_id) => ({ city_id })),
    start_date: v.start_date, end_date: v.end_date || null, terms: v.terms || null };
}

export function TermsForm({ value, onChange, onSubmit, loading, submitLabel }: { value: Terms; onChange: (v: Terms) => void; onSubmit: () => void; loading?: boolean; submitLabel: string }) {
  const t = useTranslations("authorizations");
  const cats = useCategories();
  const cities = useCities();
  const agreements = useApiQuery<Agreement[]>(["agreements"], "/supplier/commission-agreements");
  const v = value;
  const toggle = (k: "category_ids" | "city_ids", id: number) => onChange({ ...v, [k]: v[k].includes(id) ? v[k].filter((x) => x !== id) : [...v[k], id] });
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("type")}>{(id) => <Select id={id} value={v.type} onChange={(e) => onChange({ ...v, type: e.target.value })}>{["full_sales", "order_taking", "promotion_only"].map((x) => <option key={x} value={x}>{t(`types.${x}`)}</option>)}</Select>}</Field>
        <Field label={t("commission")} hint={!agreements.data?.length ? t("create_agreement_first") : undefined}>{(id) => <Select id={id} value={v.agreement_id} onChange={(e) => onChange({ ...v, agreement_id: e.target.value })} data-testid="agreement-select"><option value="">—</option>{agreements.data?.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</Select>}</Field>
        <Field label={t("start_date")}>{(id) => <Input id={id} type="date" value={v.start_date} onChange={(e) => onChange({ ...v, start_date: e.target.value })} />}</Field>
        <Field label={t("end_date")}>{(id) => <Input id={id} type="date" value={v.end_date} min={v.start_date} onChange={(e) => onChange({ ...v, end_date: e.target.value })} />}</Field>
      </div>
      <div>
        <Checkbox checked={v.all_products} onChange={(e) => onChange({ ...v, all_products: e.target.checked })} label={t("all_products")} />
        {!v.all_products && <div className="mt-2 flex flex-wrap gap-2">{cats.data?.map((c) => <button key={c.id} type="button" onClick={() => toggle("category_ids", c.id)} className={`rounded-full px-3 py-1 text-xs ring-1 ${v.category_ids.includes(c.id) ? "bg-teal-500 text-white" : "ring-line"}`}>{c.name}</button>)}</div>}
      </div>
      <div>
        <Checkbox checked={v.all_areas} onChange={(e) => onChange({ ...v, all_areas: e.target.checked })} label={t("all_areas")} />
        {!v.all_areas && <div className="mt-2 flex flex-wrap gap-2">{cities.data?.map((c) => <button key={c.id} type="button" onClick={() => toggle("city_ids", c.id)} className={`rounded-full px-3 py-1 text-xs ring-1 ${v.city_ids.includes(c.id) ? "bg-navy-700 text-white" : "ring-line"}`} data-testid={`city-${c.id}`}>{c.name}</button>)}</div>}
      </div>
      <Field label={t("terms")}>{(id) => <Textarea id={id} rows={4} value={v.terms} onChange={(e) => onChange({ ...v, terms: e.target.value })} placeholder={t("terms_placeholder")} />}</Field>
      <div className="flex justify-end"><Button loading={loading} onClick={onSubmit} disabled={(!v.all_products && !v.category_ids.length) || (!v.all_areas && !v.city_ids.length) || (v.type !== "promotion_only" && !v.agreement_id)} data-testid="issue-terms">{submitLabel}</Button></div>
    </div>
  );
}

export function useTermsState() {
  return useState<Terms>(defaultTerms());
}
