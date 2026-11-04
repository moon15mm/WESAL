"use client";

import { useQueryClient } from "@tanstack/react-query";
import { KeyRound, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Button, Field, Input } from "@/components/ui/primitives";
import { Link, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { useApiAction } from "@/lib/useApiForm";

function LoginInner() {
  const t = useTranslations("auth");
  const router = useRouter();
  const qc = useQueryClient();
  const next = useSearchParams().get("next");
  const [step, setStep] = useState<"credentials" | "mfa">("credentials");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const { loading, error, run } = useApiAction();

  const done = async () => {
    await qc.invalidateQueries({ queryKey: ["me"] });
    router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/app");
  };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const res = await run(() => api<{ mfa_required: boolean }>("/auth/login", { body: { identifier, password } }), { silent: true });
    if (!res) return;
    if (res.mfa_required) setStep("mfa");
    else await done();
  }

  async function submitMfa(e: React.FormEvent) {
    e.preventDefault();
    const ok = await run(() => api("/auth/mfa/verify", { body: { code } }), { silent: true });
    if (ok) await done();
  }

  if (step === "mfa")
    return (
      <form onSubmit={submitMfa} className="space-y-5" data-testid="mfa-form">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-teal-50 text-teal-600"><ShieldCheck className="h-6 w-6" /></div>
        <div>
          <h1 className="text-2xl font-bold text-navy-700">{t("mfa_title")}</h1>
          <p className="mt-1 text-sm text-muted">{t("mfa_subtitle")}</p>
        </div>
        <Field label={t("mfa_code")} error={error}>
          {(id) => <Input id={id} value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" dir="ltr" className="tabular text-center text-lg tracking-[0.4em]" autoFocus required />}
        </Field>
        <Button type="submit" loading={loading} className="w-full" size="lg">{t("verify")}</Button>
        <p className="text-xs text-muted">{t("mfa_recovery_hint")}</p>
      </form>
    );

  return (
    <form onSubmit={submit} className="space-y-5" data-testid="login-form">
      <div>
        <h1 className="text-2xl font-bold text-navy-700">{t("login_title")}</h1>
        <p className="mt-1 text-sm text-muted">{t("login_subtitle")}</p>
      </div>
      <Field label={t("identifier")}>
        {(id) => <Input id={id} name="identifier" value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoComplete="username" required placeholder={t("identifier_placeholder")} />}
      </Field>
      <Field label={t("password")}>
        {(id) => <Input id={id} name="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />}
      </Field>
      {error && <p className="rounded-md bg-danger/5 px-3 py-2 text-sm text-danger" role="alert">{error}</p>}
      <div className="flex justify-end">
        <Link href="/forgot-password" className="text-sm font-medium text-teal-600 hover:underline">{t("forgot")}</Link>
      </div>
      <Button type="submit" loading={loading} className="w-full" size="lg" icon={<KeyRound className="h-4 w-4" />}>{t("login")}</Button>
      <p className="text-center text-sm text-muted">
        {t("no_account")} <Link href="/register" className="font-semibold text-teal-600 hover:underline">{t("create_account")}</Link>
      </p>
    </form>
  );
}

export default function LoginPage() {
  return <Suspense><LoginInner /></Suspense>;
}
