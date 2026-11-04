"use client";

import { MailCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button, Field, Input } from "@/components/ui/primitives";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { useApiAction } from "@/lib/useApiForm";

export default function ForgotPage() {
  const t = useTranslations("auth");
  const [identifier, setIdentifier] = useState("");
  const [sent, setSent] = useState(false);
  const { loading, run } = useApiAction();
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (await run(() => api("/auth/password/forgot", { body: { identifier } }))) setSent(true);
  }
  if (sent)
    return (
      <div className="space-y-4 text-center">
        <MailCheck className="mx-auto h-12 w-12 text-teal-500" />
        <h1 className="text-xl font-bold text-navy-700">{t("forgot_sent_title")}</h1>
        <p className="text-sm text-muted">{t("forgot_sent_text")}</p>
        <Link href={`/reset-password?identifier=${encodeURIComponent(identifier)}`} className="inline-block font-semibold text-teal-600">{t("have_code")}</Link>
      </div>
    );
  return (
    <form onSubmit={submit} className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-navy-700">{t("forgot_title")}</h1>
        <p className="mt-1 text-sm text-muted">{t("forgot_subtitle")}</p>
      </div>
      <Field label={t("identifier")}>{(id) => <Input id={id} value={identifier} onChange={(e) => setIdentifier(e.target.value)} required />}</Field>
      <Button type="submit" loading={loading} className="w-full" size="lg">{t("send_reset")}</Button>
      <p className="text-center text-sm"><Link href="/login" className="text-teal-600">{t("back_to_login")}</Link></p>
    </form>
  );
}
