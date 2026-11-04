"use client";

import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { TermsForm, termsBody, useTermsState } from "@/components/app/authTerms";
import { Card, PageHeader } from "@/components/ui/layout";
import { Field, Select } from "@/components/ui/primitives";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/list";
import { useApiAction } from "@/lib/useApiForm";

type Rep = { id: string; display_name: string };

function NewAuth() {
  const t = useTranslations("authorizations");
  const router = useRouter();
  const sp = useSearchParams();
  const mine = useApiQuery<Rep[]>(["sup-reps"], "/supplier/reps");
  const [rep, setRep] = useState(sp.get("rep") || "");
  const [terms, setTerms] = useTermsState();
  const { loading, run } = useApiAction();
  return (
    <>
      <PageHeader title={t("new")} subtitle={t("new_subtitle")} />
      <Card className="max-w-3xl space-y-4">
        <Field label={t("representative")} hint={t("rep_hint")}>{(id) => <Select id={id} value={rep} onChange={(e) => setRep(e.target.value)}><option value="">—</option>{mine.data?.map((r) => <option key={r.id} value={r.id}>{r.display_name}</option>)}{sp.get("rep") && !mine.data?.some((r) => r.id === sp.get("rep")) && <option value={sp.get("rep")!}>{sp.get("name") || sp.get("rep")}</option>}</Select>}</Field>
        <TermsForm value={terms} onChange={setTerms} loading={loading} submitLabel={t("issue")} onSubmit={async () => {
          const a = await run(() => api<{ id: string }>("/supplier/authorizations", { body: { ...termsBody(terms), representative_id: rep, issue: true } }), { success: t("issued") });
          if (a) router.push(`/app/supplier/authorizations/${a.id}`);
        }} />
      </Card>
    </>
  );
}

export default function Page() {
  return <Suspense><NewAuth /></Suspense>;
}
