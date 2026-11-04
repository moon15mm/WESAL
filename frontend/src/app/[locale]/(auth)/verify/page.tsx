"use client";

import { CheckCircle2, Mail, Smartphone } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button, Input } from "@/components/ui/primitives";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useApiAction } from "@/lib/useApiForm";

function Row({ channel, verified, target }: { channel: "email" | "sms"; verified: boolean; target: string | null }) {
  const t = useTranslations("auth");
  const { refresh } = useSession();
  const [code, setCode] = useState("");
  const { loading, run } = useApiAction();
  const Icon = channel === "email" ? Mail : Smartphone;
  if (!target) return null;
  return (
    <div className="rounded-xl border border-line p-4">
      <div className="flex items-center gap-3">
        <Icon className="h-5 w-5 text-navy-400" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-navy-700">{t(channel === "email" ? "email" : "phone")}</p>
          <p className="ltr truncate text-sm text-muted">{target}</p>
        </div>
        {verified && <span className="flex items-center gap-1 text-sm font-medium text-success"><CheckCircle2 className="h-4 w-4" />{t("verified")}</span>}
      </div>
      {!verified && (
        <div className="mt-3 flex gap-2">
          <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="000000" inputMode="numeric" dir="ltr" className="tabular tracking-[0.3em]" data-testid={`code-${channel}`} />
          <Button loading={loading} onClick={async () => { if (await run(() => api("/auth/verify/confirm", { body: { channel, code } }), { success: t("verified") })) await refresh(); }}>{t("verify")}</Button>
          <Button variant="ghost" onClick={() => run(() => api("/auth/verify/request", { body: { channel } }), { success: t("code_sent") })}>{t("resend")}</Button>
        </div>
      )}
    </div>
  );
}

export default function VerifyPage() {
  const t = useTranslations("auth");
  const { me } = useSession();
  if (!me) return <p className="text-sm text-muted"><Link href="/login" className="text-teal-600">{t("login")}</Link></p>;
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-navy-700">{t("verify_title")}</h1>
        <p className="mt-1 text-sm text-muted">{t("verify_subtitle")}</p>
      </div>
      <Row channel="email" verified={me.email_verified} target={me.email} />
      <Row channel="sms" verified={me.phone_verified} target={me.phone} />
      <Link href="/app" className="inline-flex h-11 w-full items-center justify-center rounded-md bg-navy-700 font-semibold text-white" data-testid="go-dashboard">{t("continue")}</Link>
    </div>
  );
}
