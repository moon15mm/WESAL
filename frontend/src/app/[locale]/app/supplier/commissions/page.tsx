"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { CommissionTable, type Commission } from "@/components/app/commissions";
import { Pagination, Tabs } from "@/components/ui/data";
import { Card, CardHeader, EmptyState, PageHeader, Stat } from "@/components/ui/layout";
import { Modal } from "@/components/ui/overlay";
import { Button, Checkbox, Field, Input, Select, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useCategories } from "@/lib/hooks";
import { useApiQuery, useList } from "@/lib/list";
import { useSession } from "@/lib/session";
import { useApiAction } from "@/lib/useApiForm";

type Agreement = { id: string; name: string; hold_days: number; eligible_after: string; rules: { basis: string; rate: string; scope: string; category_id: number | null }[] };
type Rule = { basis: string; rate: string; scope: string; category_id: string };

export default function SupplierCommissions() {
  const t = useTranslations("commissions");
  const f = useFormat();
  const qc = useQueryClient();
  const cats = useCategories();
  const { can } = useSession();
  const manage = can("supplier.commissions.manage");
  const [tab, setTab] = useState<"list" | "agreements">("list");
  const [status, setStatus] = useState("");
  const list = useList<Commission>(tab === "list" ? "/supplier/commissions" : null, { status });
  const agreements = useApiQuery<Agreement[]>(["agreements"], "/supplier/commission-agreements");
  const summary = (list.data?.summary || {}) as Record<string, { amount: string }>;
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [pay, setPay] = useState(false);
  const [payV, setPayV] = useState({ method: "bank_transfer", reference: "" });
  const [resolve, setResolve] = useState<Commission | null>(null);
  const [resV, setResV] = useState({ accept: true, resolution: "", resolved_amount: "" });
  const [ag, setAg] = useState<{ name: string; hold_days: string; rules: Rule[] } | null>(null);
  const { loading, run } = useApiAction();
  const rows = list.data?.items || [];
  const selected = rows.filter((r) => sel.has(r.id));
  const refresh = () => { setSel(new Set()); qc.invalidateQueries({ queryKey: ["/supplier/commissions"] }); };
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("supplier_subtitle")} actions={tab === "agreements" && manage && <Button icon={<Plus className="h-4 w-4" />} onClick={() => setAg({ name: "", hold_days: "7", rules: [{ basis: "percent", rate: "3", scope: "all", category_id: "" }] })} data-testid="new-agreement">{t("new_agreement")}</Button>} />
      <div className="mb-4"><Tabs value={tab} onChange={setTab} items={[{ value: "list", label: t("commissions") }, { value: "agreements", label: t("agreements") }]} /></div>
      {tab === "list" ? (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {([["expected", ["estimated", "pending"]], ["status.due", ["due"]], ["status.approved", ["approved"]], ["status.paid", ["paid", "adjusted"]]] as const).map(([label, ks]) => (
              <Stat key={label} label={t(label)} value={f.money(ks.reduce((a, k) => a + Number(summary[k]?.amount || 0), 0))} />
            ))}
          </div>
          <div className="my-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <Tabs value={status} onChange={(x) => { setStatus(x); list.reset(); }} items={["", "due", "approved", "paid", "disputed", "estimated", "pending"].map((s) => ({ value: s, label: s ? t(`status.${s}`) : t("all") }))} />
            {manage && selected.length > 0 && (
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={!selected.every((c) => c.status === "due")} loading={loading} onClick={async () => { if (await run(() => api("/supplier/commissions/approve", { body: { commission_ids: selected.map((c) => c.id) } }), { success: t("approved") })) refresh(); }}>{t("approve_n", { n: selected.length })}</Button>
                <Button size="sm" disabled={!selected.every((c) => c.status === "approved") || new Set(selected.map((c) => c.representative?.id)).size !== 1} onClick={() => setPay(true)}>{t("record_payment")}</Button>
              </div>
            )}
          </div>
          <Card padded={false}>
            <CommissionTable rows={rows} loading={list.isLoading} side="supplier" selected={manage ? sel : undefined} onSelect={manage ? (id, v) => setSel((s) => { const n = new Set(s); if (v) n.add(id); else n.delete(id); return n; }) : undefined} onResolve={manage ? (c) => setResolve(c) : undefined} />
            {list.data && <Pagination page={list.page} pageSize={list.pageSize} total={list.data.total} onPage={list.setPage} />}
          </Card>
        </>
      ) : agreements.data?.length ? (
        <div className="grid gap-4 md:grid-cols-2">{agreements.data.map((a) => (
          <Card key={a.id}>
            <CardHeader title={a.name} subtitle={t("hold_days", { n: a.hold_days })} />
            <ul className="space-y-1.5 text-sm">{a.rules.map((r, i) => <li key={i} className="flex justify-between rounded bg-page px-3 py-1.5"><span>{r.scope === "category" ? cats.data?.find((c) => c.id === r.category_id)?.name : t(`scopes.${r.scope}`)}</span><span className="tabular font-semibold">{r.basis === "percent" ? `${r.rate}%` : `${f.money(r.rate)} ${t(`basis.${r.basis}`)}`}</span></li>)}</ul>
          </Card>
        ))}</div>
      ) : <Card><EmptyState title={t("no_agreements")} description={t("agreements_hint")} /></Card>}

      <Modal open={pay} onOpenChange={setPay} title={t("record_payment")} description={t("payment_hint", { amount: f.money(selected.reduce((a, c) => a + Number(c.amount), 0)) })}
        footer={<><Button variant="outline" onClick={() => setPay(false)}>{t("cancel")}</Button><Button loading={loading} onClick={async () => {
          const fd = new FormData(); fd.set("commission_ids", selected.map((c) => c.id).join(",")); fd.set("method", payV.method); if (payV.reference) fd.set("reference", payV.reference);
          if (await run(() => api("/supplier/commission-payments", { form: fd }), { success: t("paid_ok") })) { setPay(false); refresh(); }
        }}>{t("save")}</Button></>}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("method")}>{(id) => <Select id={id} value={payV.method} onChange={(e) => setPayV({ ...payV, method: e.target.value })}>{["bank_transfer", "cash", "cheque", "other"].map((m) => <option key={m} value={m}>{t(`methods.${m}`)}</option>)}</Select>}</Field>
          <Field label={t("reference")}>{(id) => <Input id={id} value={payV.reference} onChange={(e) => setPayV({ ...payV, reference: e.target.value })} />}</Field>
        </div>
      </Modal>
      <Modal open={!!resolve} onOpenChange={(v) => !v && setResolve(null)} title={t("resolve")} description={resolve?.disputes.find((d) => d.status === "open")?.reason}
        footer={<><Button variant="outline" onClick={() => setResolve(null)}>{t("cancel")}</Button><Button loading={loading} disabled={resV.resolution.length < 5} onClick={async () => {
          const d = resolve!.disputes.find((x) => x.status === "open")!;
          if (await run(() => api(`/supplier/commission-disputes/${d.id}/resolve`, { body: { accept: resV.accept, resolution: resV.resolution, resolved_amount: resV.accept && resV.resolved_amount ? resV.resolved_amount : null } }), { success: t("saved") })) { setResolve(null); refresh(); }
        }}>{t("save")}</Button></>}>
        <div className="space-y-3">
          <Checkbox checked={resV.accept} onChange={(e) => setResV({ ...resV, accept: e.target.checked })} label={t("accept_dispute")} />
          {resV.accept && <Field label={t("resolved_amount")}>{(id) => <Input id={id} type="number" step="0.01" value={resV.resolved_amount} onChange={(e) => setResV({ ...resV, resolved_amount: e.target.value })} />}</Field>}
          <Field label={t("resolution")}>{(id) => <Textarea id={id} value={resV.resolution} onChange={(e) => setResV({ ...resV, resolution: e.target.value })} />}</Field>
        </div>
      </Modal>
      {ag && (
        <Modal open onOpenChange={(v) => !v && setAg(null)} size="lg" title={t("new_agreement")} footer={<><Button variant="outline" onClick={() => setAg(null)}>{t("cancel")}</Button><Button loading={loading} disabled={!ag.name} data-testid="save-agreement" onClick={async () => {
          const body = { name: ag.name, hold_days: Number(ag.hold_days), rules: ag.rules.map((r) => ({ basis: r.basis, rate: r.rate, scope: r.scope, category_id: r.scope === "category" ? Number(r.category_id) : null })) };
          if (await run(() => api("/supplier/commission-agreements", { body }), { success: t("saved") })) { setAg(null); qc.invalidateQueries({ queryKey: ["agreements"] }); }
        }}>{t("save")}</Button></>}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("name")}>{(id) => <Input id={id} value={ag.name} onChange={(e) => setAg({ ...ag, name: e.target.value })} />}</Field>
            <Field label={t("hold_days_label")} hint={t("hold_days_hint")}>{(id) => <Input id={id} type="number" min={0} value={ag.hold_days} onChange={(e) => setAg({ ...ag, hold_days: e.target.value })} />}</Field>
          </div>
          <div className="mt-4 space-y-2">
            {ag.rules.map((r, i) => (
              <div key={i} className="grid grid-cols-2 gap-2 rounded-md border border-line p-2 sm:grid-cols-[1fr_1fr_100px_1fr_auto]">
                <Select value={r.basis} onChange={(e) => setAg({ ...ag, rules: ag.rules.map((x, j) => (j === i ? { ...x, basis: e.target.value } : x)) })}>{["percent", "per_unit", "fixed_per_order"].map((b) => <option key={b} value={b}>{t(`basis_names.${b}`)}</option>)}</Select>
                <Select value={r.scope} onChange={(e) => setAg({ ...ag, rules: ag.rules.map((x, j) => (j === i ? { ...x, scope: e.target.value } : x)) })}>{["all", "category"].map((s) => <option key={s} value={s}>{t(`scopes.${s}`)}</option>)}</Select>
                <Input type="number" step="0.01" value={r.rate} onChange={(e) => setAg({ ...ag, rules: ag.rules.map((x, j) => (j === i ? { ...x, rate: e.target.value } : x)) })} aria-label={t("rate")} />
                {r.scope === "category" ? <Select value={r.category_id} onChange={(e) => setAg({ ...ag, rules: ag.rules.map((x, j) => (j === i ? { ...x, category_id: e.target.value } : x)) })}><option value="">—</option>{cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select> : <span />}
                <button className="p-2 text-muted hover:text-danger" onClick={() => setAg({ ...ag, rules: ag.rules.filter((_, j) => j !== i) })} aria-label="remove"><Trash2 className="h-4 w-4" /></button>
              </div>
            ))}
            <Button variant="ghost" size="sm" icon={<Plus className="h-4 w-4" />} onClick={() => setAg({ ...ag, rules: [...ag.rules, { basis: "percent", rate: "2", scope: "category", category_id: "" }] })}>{t("add_rule")}</Button>
          </div>
        </Modal>
      )}
    </>
  );
}
