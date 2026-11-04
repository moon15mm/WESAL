"use client";

import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Button, Field, Input } from "@/components/ui/primitives";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { useApiAction } from "@/lib/useApiForm";

function ResetInner() {
  const t = useTranslations("auth");
  const sp = useSearchParams();
  const router = useRouter();
  const [identifier, setIdentifier] = useState(sp.get("email") || sp.get("identifier") || "");
  const [code, setCode] = useState(sp.get("token") || "");
  const [password, setPassword] = useState("");
  const { loading, fields, run } = useApiAction();
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const ok = await run(() => api("/auth/password/reset", { body: { identifier, code, new_password: password } }), { success: t("reset_done") });
    if (ok) router.replace("/login");
  }
  return (
    <form onSubmit={submit} className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-navy-700">{t("reset_title")}</h1>
        <p className="mt-1 text-sm text-muted">{t("reset_subtitle")}</p>
      </div>
      <Field label={t("identifier")}>{(id) => <Input id={id} value={identifier} onChange={(e) => setIdentifier(e.target.value)} required />}</Field>
      {!sp.get("token") && <Field label={t("code")}>{(id) => <Input id={id} value={code} onChange={(e) => setCode(e.target.value)} dir="ltr" required />}</Field>}
      <Field label={t("new_password")} hint={t("password_hint")} error={fields.password ? t("weak_password") : undefined}>
        {(id) => <Input id={id} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" required minLength={10} />}
      </Field>
      <Button type="submit" loading={loading} className="w-full" size="lg">{t("set_password")}</Button>
    </form>
  );
}

export default function ResetPage() {
  return <Suspense><ResetInner /></Suspense>;
}
