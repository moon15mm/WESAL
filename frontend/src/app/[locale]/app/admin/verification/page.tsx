"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { DataTable, Pagination, Tabs, type Column } from "@/components/ui/data";
import { Card, KV, PageHeader, StatusBadge } from "@/components/ui/layout";
import { Modal } from "@/components/ui/overlay";
import { Button, Field, Select, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useApiQuery, useList } from "@/lib/list";
import { useApiAction } from "@/lib/useApiForm";

type Biz = { id: string; name: string; type: string; verification_status: string; cr_number: string | null; created_at: string; city: { name: string } | null };
type BizDetail = Biz & { legal_name: string; vat_number: string | null; email: string | null; phone: string | null; documents: { id: string; doc_type: string; number: string | null; status: string; file_url: string }[]; members: { name: string; role: string }[] };
type Rep = { id: string; display_name: string; kind: string; verification_status: string; phone: string | null; email: string | null; created_at: string; freelance_doc_number: string | null; documents: { id: string; doc_type: string; status: string; file_url: string }[] };

export default function Verification() {
  const t = useTranslations("admin");
  const f = useFormat();
  const qc = useQueryClient();
  const [tab, setTab] = useState<"businesses" | "reps">("businesses");
  const [status, setStatus] = useState("pending");
  const [type, setType] = useState("");
  const biz = useList<Biz>(tab === "businesses" ? "/admin/businesses" : null, { verification: status, type });
  const reps = useList<Rep>(tab === "reps" ? "/admin/representatives" : null, { verification: status });
  const [openBiz, setOpenBiz] = useState<string | null>(null);
  const [openRep, setOpenRep] = useState<Rep | null>(null);
  const detail = useApiQuery<BizDetail>(["admin-biz", openBiz], openBiz ? `/admin/businesses/${openBiz}` : null);
  const [docs, setDocs] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const { loading, run } = useApiAction();
  const decide = async (decision: "verify" | "reject") => {
    const path = openBiz ? `/admin/businesses/${openBiz}/verification` : `/admin/representatives/${openRep!.id}/verification`;
    if (await run(() => api(path, { body: { decision, reason: reason || null, documents: docs } }), { success: t("saved") })) {
      setOpenBiz(null); setOpenRep(null); setDocs({}); setReason("");
      qc.invalidateQueries({ queryKey: ["/admin/businesses"] }); qc.invalidateQueries({ queryKey: ["/admin/representatives"] });
    }
  };
  const docRows = openBiz ? detail.data?.documents || [] : openRep?.documents || [];
  const bizCols: Column<Biz>[] = [
    { key: "n", header: t("name"), cell: (b) => <span className="font-medium">{b.name}</span> },
    { key: "t", header: t("type"), cell: (b) => t(`btypes.${b.type}`) },
    { key: "cr", header: t("cr"), cell: (b) => <span className="ltr">{b.cr_number || "—"}</span> },
    { key: "s", header: t("status"), cell: (b) => <StatusBadge status={b.verification_status} /> },
    { key: "d", header: t("date"), hideOnMobile: true, cell: (b) => f.date(b.created_at) },
  ];
  const repCols: Column<Rep>[] = [
    { key: "n", header: t("name"), cell: (r) => <span className="font-medium">{r.display_name}</span> },
    { key: "k", header: t("type"), cell: (r) => t(`rkinds.${r.kind}`) },
    { key: "p", header: t("phone"), cell: (r) => <span className="ltr">{r.phone}</span> },
    { key: "s", header: t("status"), cell: (r) => <StatusBadge status={r.verification_status} /> },
    { key: "d", header: t("date"), hideOnMobile: true, cell: (r) => f.date(r.created_at) },
  ];
  return (
    <>
      <PageHeader title={t("verification_title")} subtitle={t("verification_subtitle")} />
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:justify-between">
        <Tabs value={tab} onChange={setTab} items={[{ value: "businesses", label: t("businesses") }, { value: "reps", label: t("representatives") }]} />
        <div className="flex gap-2">
          <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-40">{["", "pending", "unverified", "verified", "rejected"].map((s) => <option key={s} value={s}>{s ? t(`vstatus.${s}`) : t("all")}</option>)}</Select>
          {tab === "businesses" && <Select value={type} onChange={(e) => setType(e.target.value)} className="w-36"><option value="">{t("all")}</option><option value="supplier">{t("btypes.supplier")}</option><option value="retailer">{t("btypes.retailer")}</option></Select>}
        </div>
      </div>
      <Card padded={false}>
        {tab === "businesses" ? <DataTable columns={bizCols} rows={biz.data?.items} loading={biz.isLoading} rowKey={(b) => b.id} onRowClick={(b) => setOpenBiz(b.id)} /> : <DataTable columns={repCols} rows={reps.data?.items} loading={reps.isLoading} rowKey={(r) => r.id} onRowClick={setOpenRep} />}
        {tab === "businesses" && biz.data && <Pagination page={biz.page} pageSize={biz.pageSize} total={biz.data.total} onPage={biz.setPage} />}
        {tab === "reps" && reps.data && <Pagination page={reps.page} pageSize={reps.pageSize} total={reps.data.total} onPage={reps.setPage} />}
      </Card>
      {(openBiz || openRep) && (
        <Modal open onOpenChange={(v) => { if (!v) { setOpenBiz(null); setOpenRep(null); } }} size="lg" title={openBiz ? detail.data?.name || "…" : openRep!.display_name}
          footer={<><Button variant="ghost" className="text-danger" disabled={!reason} loading={loading} onClick={() => decide("reject")}>{t("reject")}</Button><Button variant="success" loading={loading} onClick={() => decide("verify")} data-testid="verify-account">{t("verify")}</Button></>}>
          {openBiz && detail.data && <KV items={[[t("legal_name"), detail.data.legal_name], [t("cr"), detail.data.cr_number], [t("vat"), detail.data.vat_number], [t("email"), detail.data.email], [t("phone"), detail.data.phone], [t("members"), detail.data.members.map((m) => m.name).join("، ")]]} />}
          {openRep && <KV items={[[t("phone"), openRep.phone], [t("email"), openRep.email], [t("freelance"), openRep.freelance_doc_number]]} />}
          <p className="mb-2 mt-5 text-sm font-semibold">{t("documents")}</p>
          <ul className="space-y-2">{docRows.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line p-2 text-sm">
              <a href={d.file_url} target="_blank" className="text-teal-700 underline">{d.doc_type}</a>
              <div className="flex items-center gap-2"><StatusBadge status={d.status} /><Select className="h-8 w-32 text-xs" value={docs[d.id] || ""} onChange={(e) => setDocs({ ...docs, [d.id]: e.target.value })}><option value="">—</option><option value="approved">{t("approve")}</option><option value="rejected">{t("reject")}</option></Select></div>
            </li>
          ))}</ul>
          {!docRows.length && <p className="text-sm text-muted">{t("no_documents")}</p>}
          <Field label={t("rejection_reason")} className="mt-4">{(id) => <Textarea id={id} value={reason} onChange={(e) => setReason(e.target.value)} />}</Field>
        </Modal>
      )}
    </>
  );
}
