"use client";

import { useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Building2, Send } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Pagination, SearchInput } from "@/components/ui/data";
import { Alert, Badge, Card, CardHeader, EmptyState, PageHeader, SkeletonRows, StatusBadge } from "@/components/ui/layout";
import { Modal } from "@/components/ui/overlay";
import { Button, Field, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useCategories } from "@/lib/hooks";
import { useApiQuery, useList } from "@/lib/list";
import { useSession } from "@/lib/session";
import type { BusinessBrief } from "@/lib/types";
import { useApiAction } from "@/lib/useApiForm";

type Mine = { supplier: BusinessBrief; relation: string; status: string; authorizations: { id: string; number: string; status: string }[] };
type Supplier = BusinessBrief & { products_count: number; description: string | null };

export default function Companies() {
  const t = useTranslations("companies");
  const qc = useQueryClient();
  const { me } = useSession();
  const cats = useCategories();
  const mine = useApiQuery<Mine[]>(["rep-companies"], "/rep/companies");
  const auths = useApiQuery<{ supplier: { id: string }; status: string }[]>(["rep-auths"], "/rep/authorizations");
  const [q, setQ] = useState("");
  const list = useList<Supplier>("/market/suppliers", { q }, 12);
  const [req, setReq] = useState<Supplier | null>(null);
  const [msg, setMsg] = useState("");
  const [catIds, setCatIds] = useState<number[]>([]);
  const { loading, run } = useApiAction();
  const open = new Set((auths.data || []).filter((a) => ["sent", "pending_rep", "active", "suspended", "draft"].includes(a.status)).map((a) => a.supplier.id));
  const verified = me?.representative?.verification_status === "verified";
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("subtitle")} />
      {!verified && <div className="mb-4"><Alert tone="warning">{t("verify_first")}</Alert></div>}
      {mine.data && mine.data.length > 0 && (
        <Card className="mb-6">
          <CardHeader title={t("my_companies")} />
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {mine.data.map((m) => (
              <div key={m.supplier.id} className="rounded-md border border-line p-3">
                <p className="font-semibold text-navy-700">{m.supplier.name}</p>
                <div className="mt-1 flex flex-wrap gap-1"><Badge tone="teal">{t(`relations.${m.relation}`)}</Badge>{m.authorizations.slice(-1).map((a) => <StatusBadge key={a.id} status={a.status} />)}</div>
              </div>
            ))}
          </div>
        </Card>
      )}
      <SearchInput value={q} onChange={(v) => { setQ(v); list.reset(); }} className="mb-4 sm:w-80" placeholder={t("search")} />
      {list.isLoading ? <SkeletonRows /> : list.data?.items.length ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {list.data.items.map((s) => (
              <Card key={s.id} className="flex flex-col">
                <div className="flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-lg bg-navy-50"><Building2 className="h-5 w-5 text-navy-300" /></span><div><p className="flex items-center gap-1 font-semibold text-navy-700">{s.name}<BadgeCheck className="h-4 w-4 text-teal-500" /></p><p className="text-xs text-muted">{s.city?.name} · {t("products", { n: s.products_count })}</p></div></div>
                {s.description && <p className="mt-3 line-clamp-2 flex-1 text-sm text-muted">{s.description}</p>}
                <Button className="mt-4 self-start" size="sm" icon={<Send className="h-4 w-4" />} disabled={open.has(s.id) || !verified} onClick={() => setReq(s)} data-testid="request-authorization">{open.has(s.id) ? t("already_requested") : t("request")}</Button>
              </Card>
            ))}
          </div>
          <Card padded={false} className="mt-4"><Pagination page={list.page} pageSize={list.pageSize} total={list.data.total} onPage={list.setPage} /></Card>
        </>
      ) : <Card><EmptyState title={t("empty")} /></Card>}
      <Modal open={!!req} onOpenChange={(v) => !v && setReq(null)} title={t("request_title", { name: req?.name || "" })} description={t("request_hint")}
        footer={<><Button variant="outline" onClick={() => setReq(null)}>{t("cancel")}</Button><Button loading={loading} data-testid="send-request" onClick={async () => {
          if (await run(() => api("/rep/authorizations", { body: { supplier_id: req!.id, message: msg || null, category_ids: catIds } }), { success: t("sent") })) { setReq(null); setMsg(""); qc.invalidateQueries({ queryKey: ["rep-auths"] }); }
        }}>{t("send")}</Button></>}>
        <div className="space-y-3">
          <Field label={t("message")}>{(id) => <Textarea id={id} rows={4} value={msg} onChange={(e) => setMsg(e.target.value)} placeholder={t("message_placeholder")} />}</Field>
          <div><p className="mb-2 text-sm font-medium">{t("categories")}</p><div className="flex flex-wrap gap-2">{cats.data?.map((c) => (
            <button key={c.id} type="button" onClick={() => setCatIds((x) => (x.includes(c.id) ? x.filter((y) => y !== c.id) : [...x, c.id]))} className={`rounded-full px-3 py-1 text-xs ring-1 ${catIds.includes(c.id) ? "bg-teal-500 text-white ring-teal-500" : "ring-line"}`}>{c.name}</button>
          ))}</div><p className="mt-1 text-xs text-muted">{t("categories_hint")}</p></div>
        </div>
      </Modal>
    </>
  );
}
