"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileSignature } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { DataTable, type Column } from "@/components/ui/data";
import { Alert, Card, CardHeader, KV, PageHeader, SkeletonRows, StatusBadge } from "@/components/ui/layout";
import { ConfirmDialog } from "@/components/ui/overlay";
import { Button, Checkbox } from "@/components/ui/primitives";
import { Link, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useCategories, useCities } from "@/lib/hooks";
import { useApiAction } from "@/lib/useApiForm";

export type Authorization = {
  id: string; number: string; status: string; type: string; initiated_by: string;
  supplier: { id: string; name: string }; representative: { id: string; display_name: string; kind: string; verification_status: string; rating_avg: number };
  request_message: string | null; all_products: boolean; all_areas: boolean;
  products: { product_id: string | null; category_id: number | null; brand_id: string | null }[];
  areas: { city: { name: string } | null; city_id: number; district: string | null }[];
  start_date: string | null; end_date: string | null; terms: string | null; terms_hash: string | null; accepted_at: string | null; status_reason: string | null; version: number;
  agreement: { id: string; name: string; hold_days: number; rules: { basis: string; rate: string; scope: string; category_id: number | null }[] } | null;
  history?: { action: string; from: string | null; to: string | null; reason: string | null; at: string }[];
  created_at: string;
};

export function AuthorizationTable({ rows, loading, side }: { rows?: Authorization[]; loading?: boolean; side: "rep" | "supplier" }) {
  const t = useTranslations("authorizations");
  const f = useFormat();
  const router = useRouter();
  const cols: Column<Authorization>[] = [
    { key: "n", header: t("number"), cell: (a) => <span className="ltr font-semibold">{a.number}</span> },
    side === "rep" ? { key: "s", header: t("company"), cell: (a) => a.supplier.name } : { key: "r", header: t("representative"), cell: (a) => a.representative.display_name },
    { key: "type", header: t("type"), hideOnMobile: true, cell: (a) => t(`types.${a.type}`) },
    { key: "status", header: t("status"), cell: (a) => <StatusBadge status={a.status} /> },
    { key: "end", header: t("end_date"), cell: (a) => f.date(a.end_date) },
  ];
  return <DataTable columns={cols} rows={rows} loading={loading} rowKey={(a) => a.id} onRowClick={(a) => router.push(`/app/${side}/authorizations/${a.id}`)} />;
}

export function AuthorizationDetail({ side, id, supplierActions }: { side: "rep" | "supplier"; id: string; supplierActions?: (a: Authorization, refresh: () => void) => React.ReactNode }) {
  const t = useTranslations("authorizations");
  const f = useFormat();
  const qc = useQueryClient();
  const cats = useCategories();
  const cities = useCities();
  const key = ["authorization", side, id];
  const { data: a } = useQuery({ queryKey: key, queryFn: () => api<Authorization>(`/${side}/authorizations/${id}`) });
  const [agree, setAgree] = useState(false);
  const [decline, setDecline] = useState(false);
  const { loading, run } = useApiAction();
  if (!a) return <SkeletonRows />;
  const refresh = () => qc.invalidateQueries({ queryKey: key });
  const catName = (cid: number | null) => cats.data?.find((c) => c.id === cid)?.name || cid;
  return (
    <>
      <PageHeader back={<Link href={`/app/${side}/authorizations`} className="mb-2 inline-block text-sm text-teal-600">← {t("title")}</Link>}
        title={<span className="flex flex-wrap items-center gap-3"><span className="ltr">{a.number}</span><StatusBadge status={a.status} /></span>}
        subtitle={side === "rep" ? a.supplier.name : a.representative.display_name}
        actions={side === "supplier" && supplierActions?.(a, refresh)} />
      {a.status_reason && <div className="mb-4"><Alert tone="info">{a.status_reason}</Alert></div>}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader title={t("terms")} action={<FileSignature className="h-5 w-5 text-teal-500" />} />
            <KV items={[
              [t("type"), t(`types.${a.type}`)], [t("period"), `${f.date(a.start_date)} → ${a.end_date ? f.date(a.end_date) : t("open_ended")}`],
              [t("products"), a.all_products ? t("all_products") : a.products.map((p) => p.category_id ? catName(p.category_id) : t("specific_product")).join("، ")],
              [t("areas"), a.all_areas ? t("all_areas") : a.areas.map((x) => `${x.city?.name || cities.data?.find((c) => c.id === x.city_id)?.name}${x.district ? ` (${x.district})` : ""}`).join("، ")],
              [t("version"), a.version], [t("accepted_at"), f.datetime(a.accepted_at)],
            ]} />
            {a.terms && <div className="mt-4 whitespace-pre-line rounded-md bg-page p-4 text-sm leading-7">{a.terms}</div>}
          </Card>
          {a.agreement && (
            <Card>
              <CardHeader title={t("commission")} subtitle={a.agreement.name} />
              <ul className="space-y-2 text-sm">
                {a.agreement.rules.map((r, i) => (
                  <li key={i} className="flex justify-between rounded-md bg-page px-3 py-2">
                    <span>{r.scope === "all" ? t("all_products") : r.scope === "category" ? catName(r.category_id) : t(`scopes.${r.scope}`)}</span>
                    <span className="tabular font-semibold">{r.basis === "percent" ? `${f.number(r.rate)}%` : `${f.money(r.rate)} ${t(`basis.${r.basis}`)}`}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-muted">{t("hold_days", { n: a.agreement.hold_days })}</p>
            </Card>
          )}
          {side === "rep" && a.status === "pending_rep" && (
            <Card className="border-teal-200 bg-teal-50/40">
              <CardHeader title={t("accept_title")} subtitle={t("accept_hint")} />
              <Checkbox checked={agree} onChange={(e) => setAgree(e.target.checked)} label={t("i_agree")} data-testid="agree-terms" />
              <div className="mt-4 flex flex-wrap gap-2">
                <Button variant="success" icon={<CheckCircle2 className="h-4 w-4" />} disabled={!agree} loading={loading} data-testid="accept-authorization"
                  onClick={async () => { if (await run(() => api(`/rep/authorizations/${a.id}/accept`, { body: { terms_hash: a.terms_hash } }), { success: t("accepted") })) refresh(); }}>{t("accept")}</Button>
                <Button variant="ghost" className="text-danger" onClick={() => setDecline(true)}>{t("decline")}</Button>
              </div>
            </Card>
          )}
          {side === "rep" && a.status === "sent" && <Alert tone="info" title={t("waiting_company")} action={<Button variant="ghost" className="text-danger" onClick={() => setDecline(true)}>{t("withdraw")}</Button>} />}
        </div>
        <Card>
          <CardHeader title={t("history")} />
          <ol className="space-y-4 border-s border-line ps-4 text-sm">
            {a.history?.map((h, i) => <li key={i}><p className="font-medium">{t(`actions.${h.action}`)}</p><p className="text-xs text-muted">{f.datetime(h.at)}</p>{h.reason && <p className="mt-1">{h.reason}</p>}</li>)}
          </ol>
        </Card>
      </div>
      <ConfirmDialog open={decline} onOpenChange={setDecline} title={a.status === "sent" ? t("withdraw") : t("decline")} requireReason tone="danger" loading={loading}
        onConfirm={async (reason) => { if (await run(() => api(`/rep/authorizations/${a.id}/decline`, { body: { reason } }))) { setDecline(false); refresh(); } }} />
    </>
  );
}
