"use client";

import { useTranslations } from "next-intl";
import { use, useState } from "react";
import { AuthorizationDetail, type Authorization } from "@/components/app/authorizations";
import { TermsForm, defaultTerms, termsBody, type Terms } from "@/components/app/authTerms";
import { ConfirmDialog, Modal } from "@/components/ui/overlay";
import { Button, Field, Input } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useApiAction } from "@/lib/useApiForm";

export default function SupplierAuthorization({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const t = useTranslations("authorizations");
  const [modal, setModal] = useState<{ kind: string; a: Authorization; refresh: () => void } | null>(null);
  const [terms, setTerms] = useState<Terms>(defaultTerms());
  const [renew, setRenew] = useState({ start_date: new Date().toISOString().slice(0, 10), end_date: "" });
  const { loading, run } = useApiAction();
  const close = () => setModal(null);
  const fromAuth = (a: Authorization): Terms => ({ type: a.type, agreement_id: a.agreement?.id || "", all_products: a.all_products, all_areas: a.all_areas,
    category_ids: a.products.filter((p) => p.category_id).map((p) => p.category_id!), city_ids: a.areas.map((x) => x.city_id),
    start_date: a.start_date || new Date().toISOString().slice(0, 10), end_date: a.end_date || "", terms: a.terms || "" });
  return (
    <>
      <AuthorizationDetail side="supplier" id={id} supplierActions={(a, refresh) => (
        <div className="flex flex-wrap gap-2">
          {["sent", "draft"].includes(a.status) && <Button onClick={() => { setTerms(fromAuth(a)); setModal({ kind: "issue", a, refresh }); }} data-testid="open-issue">{t("approve_issue")}</Button>}
          {["pending_rep", "active"].includes(a.status) && <Button variant="outline" onClick={() => { setTerms(fromAuth(a)); setModal({ kind: "edit", a, refresh }); }}>{t("edit_terms")}</Button>}
          {a.status === "active" && <Button variant="outline" onClick={() => setModal({ kind: "suspend", a, refresh })}>{t("suspend")}</Button>}
          {a.status === "suspended" && <Button variant="outline" onClick={() => setModal({ kind: "resume", a, refresh })}>{t("resume")}</Button>}
          {["active", "expired"].includes(a.status) && <Button variant="outline" onClick={() => setModal({ kind: "renew", a, refresh })}>{t("renew")}</Button>}
          {a.status === "sent" && <Button variant="ghost" className="text-danger" onClick={() => setModal({ kind: "decline", a, refresh })}>{t("decline")}</Button>}
          {["draft", "pending_rep", "active", "suspended"].includes(a.status) && <Button variant="ghost" className="text-danger" onClick={() => setModal({ kind: "cancel", a, refresh })}>{t("cancel_auth")}</Button>}
        </div>
      )} />
      {modal && (modal.kind === "issue" || modal.kind === "edit") && (
        <Modal open onOpenChange={(v) => !v && close()} size="lg" title={t(modal.kind === "issue" ? "approve_issue" : "edit_terms")} description={t("issue_hint")}>
          <TermsForm value={terms} onChange={setTerms} loading={loading} submitLabel={t("issue")} onSubmit={async () => {
            const path = modal.kind === "issue" ? `/supplier/authorizations/${modal.a.id}/issue` : `/supplier/authorizations/${modal.a.id}`;
            if (await run(() => api(path, { method: modal.kind === "issue" ? "POST" : "PUT", body: termsBody(terms) }), { success: t("issued") })) { modal.refresh(); close(); }
          }} />
        </Modal>
      )}
      {modal && modal.kind === "renew" && (
        <Modal open onOpenChange={(v) => !v && close()} title={t("renew")} footer={<Button loading={loading} onClick={async () => { if (await run(() => api(`/supplier/authorizations/${modal.a.id}/renew`, { body: { start_date: renew.start_date, end_date: renew.end_date || null } }), { success: t("issued") })) { modal.refresh(); close(); } }}>{t("renew")}</Button>}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("start_date")}>{(fid) => <Input id={fid} type="date" value={renew.start_date} onChange={(e) => setRenew({ ...renew, start_date: e.target.value })} />}</Field>
            <Field label={t("end_date")}>{(fid) => <Input id={fid} type="date" value={renew.end_date} onChange={(e) => setRenew({ ...renew, end_date: e.target.value })} />}</Field>
          </div>
        </Modal>
      )}
      {modal && ["suspend", "resume", "cancel", "decline"].includes(modal.kind) && (
        <ConfirmDialog open onOpenChange={(v) => !v && close()} title={t(modal.kind === "cancel" ? "cancel_auth" : modal.kind)} requireReason tone={modal.kind === "resume" ? "primary" : "danger"} loading={loading}
          onConfirm={async (reason) => { if (await run(() => api(`/supplier/authorizations/${modal.a.id}/${modal.kind}`, { body: { reason } }), { success: t("saved") })) { modal.refresh(); close(); } }} />
      )}
    </>
  );
}
