"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, KeyRound, LogOut, MonitorSmartphone, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import QRCode from "qrcode";
import { Suspense, useEffect, useState } from "react";
import { Tabs } from "@/components/ui/data";
import { Alert, Badge, Card, CardHeader, PageHeader } from "@/components/ui/layout";
import { Button, Field, Input, Select, Switch } from "@/components/ui/primitives";
import { useRouter } from "@/i18n/navigation";
import { localeNames, locales } from "@/i18n/routing";
import { api, download } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useSession } from "@/lib/session";
import { useApiAction } from "@/lib/useApiForm";

type Tab = "profile" | "security" | "notifications" | "privacy";

function Profile() {
  const t = useTranslations("settings");
  const { me, refresh } = useSession();
  const router = useRouter();
  const [v, setV] = useState(() => ({ full_name: me!.full_name, locale: me!.locale, document_locale: me!.document_locale, number_system: me!.number_system, timezone: me!.timezone, currency: me!.currency }));
  const { loading, run } = useApiAction();
  return (
    <Card className="max-w-2xl">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("full_name")} className="sm:col-span-2">{(id) => <Input id={id} value={v.full_name} onChange={(e) => setV({ ...v, full_name: e.target.value })} />}</Field>
        <Field label={t("ui_language")}>{(id) => <Select id={id} value={v.locale} onChange={(e) => setV({ ...v, locale: e.target.value })}>{locales.map((l) => <option key={l} value={l}>{localeNames[l]}</option>)}</Select>}</Field>
        <Field label={t("document_language")} hint={t("document_language_hint")}>{(id) => <Select id={id} value={v.document_locale} onChange={(e) => setV({ ...v, document_locale: e.target.value })}>{locales.map((l) => <option key={l} value={l}>{localeNames[l]}</option>)}</Select>}</Field>
        <Field label={t("digits")}>{(id) => <Select id={id} value={v.number_system} onChange={(e) => setV({ ...v, number_system: e.target.value as "latn" | "arab" })}><option value="latn">0123456789</option><option value="arab">٠١٢٣٤٥٦٧٨٩</option></Select>}</Field>
        <Field label={t("currency")}>{(id) => <Select id={id} value={v.currency} onChange={(e) => setV({ ...v, currency: e.target.value })}>{["SAR", "AED", "KWD", "BHD", "QAR", "OMR", "USD", "EGP", "PKR", "INR"].map((c) => <option key={c} value={c}>{c}</option>)}</Select>}</Field>
        <Field label={t("timezone")} className="sm:col-span-2">{(id) => <Select id={id} value={v.timezone} onChange={(e) => setV({ ...v, timezone: e.target.value })}>{["Asia/Riyadh", "Asia/Dubai", "Asia/Kuwait", "Asia/Qatar", "Asia/Bahrain", "Asia/Muscat", "Africa/Cairo", "Asia/Karachi", "Asia/Kolkata", "Europe/London", "UTC"].map((z) => <option key={z} value={z}>{z}</option>)}</Select>}</Field>
      </div>
      <p className="mt-3 text-xs text-muted">{t("currency_note")}</p>
      <div className="mt-5 flex justify-end"><Button loading={loading} onClick={async () => {
        if (await run(() => api("/auth/me", { method: "PATCH", body: v }), { success: t("saved") })) { await refresh(); if (v.locale !== me!.locale) router.replace("/app/settings", { locale: v.locale }); }
      }}>{t("save")}</Button></div>
    </Card>
  );
}

function Security() {
  const t = useTranslations("settings");
  const f = useFormat();
  const qc = useQueryClient();
  const router = useRouter();
  const { me, refresh } = useSession();
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: () => api<{ id: string; created_at: string; last_seen_at: string; ip: string | null; user_agent: string | null; current: boolean }[]>("/auth/sessions") });
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string; qr?: string } | null>(null);
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState<string[] | null>(null);
  const [disable, setDisable] = useState({ password: "", code: "" });
  const { loading, run } = useApiAction();
  useEffect(() => { if (setup && !setup.qr) QRCode.toDataURL(setup.otpauth_uri, { margin: 1, width: 180 }).then((qr) => setSetup((s) => (s ? { ...s, qr } : s))); }, [setup]);
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader title={t("change_password")} action={<KeyRound className="h-5 w-5 text-navy-300" />} />
        <div className="space-y-3">
          <Field label={t("current_password")}>{(id) => <Input id={id} type="password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} autoComplete="current-password" />}</Field>
          <Field label={t("new_password")} hint={t("password_hint")}>{(id) => <Input id={id} type="password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} autoComplete="new-password" />}</Field>
          <Button loading={loading} disabled={!pw.current_password || pw.new_password.length < 10} onClick={async () => { if (await run(() => api("/auth/password/change", { body: pw }), { success: t("password_changed") })) setPw({ current_password: "", new_password: "" }); }}>{t("update_password")}</Button>
        </div>
      </Card>
      <Card>
        <CardHeader title={t("mfa")} subtitle={t("mfa_hint")} action={me?.mfa_enabled ? <Badge tone="success">{t("enabled")}</Badge> : <Badge tone="warning">{t("disabled")}</Badge>} />
        {recovery ? (
          <Alert tone="success" title={t("recovery_title")}><p className="mb-2">{t("recovery_hint")}</p><div className="ltr grid grid-cols-2 gap-1 font-mono text-sm">{recovery.map((c) => <span key={c}>{c}</span>)}</div></Alert>
        ) : me?.mfa_enabled ? (
          <div className="space-y-3">
            <Field label={t("current_password")}>{(id) => <Input id={id} type="password" value={disable.password} onChange={(e) => setDisable({ ...disable, password: e.target.value })} />}</Field>
            <Field label={t("mfa_code")}>{(id) => <Input id={id} dir="ltr" inputMode="numeric" value={disable.code} onChange={(e) => setDisable({ ...disable, code: e.target.value })} />}</Field>
            <Button variant="outline" className="text-danger" loading={loading} onClick={async () => { if (await run(() => api("/auth/mfa/disable", { body: disable }), { success: t("mfa_disabled") })) refresh(); }}>{t("disable_mfa")}</Button>
          </div>
        ) : setup ? (
          <div className="space-y-3">
            <p className="text-sm">{t("scan_qr")}</p>
            {setup.qr && <img src={setup.qr} alt="QR" className="h-44 w-44 rounded-md ring-1 ring-line" />}
            <p className="ltr break-all rounded bg-page p-2 font-mono text-xs">{setup.secret}</p>
            <Field label={t("mfa_code")}>{(id) => <Input id={id} dir="ltr" inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} data-testid="mfa-enable-code" />}</Field>
            <Button loading={loading} onClick={async () => { const r = await run(() => api<{ recovery_codes: string[] }>("/auth/mfa/enable", { body: { code } }), { success: t("mfa_enabled") }); if (r) { setRecovery(r.recovery_codes); setSetup(null); refresh(); } }}>{t("activate")}</Button>
          </div>
        ) : (
          <Button icon={<ShieldCheck className="h-4 w-4" />} loading={loading} onClick={async () => { const s = await run(() => api<{ secret: string; otpauth_uri: string }>("/auth/mfa/setup", { method: "POST" })); if (s) setSetup(s); }} data-testid="mfa-setup">{t("setup_mfa")}</Button>
        )}
      </Card>
      <Card className="lg:col-span-2">
        <CardHeader title={t("sessions")} subtitle={t("sessions_hint")} action={<Button variant="outline" size="sm" icon={<LogOut className="h-4 w-4" />} onClick={async () => { if (await run(() => api("/auth/logout-all", { method: "POST" }))) { qc.clear(); router.replace("/login"); } }}>{t("logout_all")}</Button>} />
        <ul className="divide-y divide-line">
          {sessions.data?.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-3 py-3 text-sm">
              <span className="flex min-w-0 items-center gap-3"><MonitorSmartphone className="h-5 w-5 shrink-0 text-navy-300" /><span className="min-w-0"><span className="block truncate">{s.user_agent || "—"}</span><span className="ltr block text-xs text-muted">{s.ip} · {f.datetime(s.last_seen_at)}</span></span></span>
              {s.current ? <Badge tone="teal">{t("this_device")}</Badge> : <Button size="sm" variant="ghost" className="text-danger" onClick={async () => { if (await run(() => api(`/auth/sessions/${s.id}`, { method: "DELETE" }))) qc.invalidateQueries({ queryKey: ["sessions"] }); }}>{t("revoke")}</Button>}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function NotificationPrefs() {
  const t = useTranslations("settings");
  const tn = useTranslations("events");
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["prefs"], queryFn: () => api<{ channels: Record<string, boolean>; events: { event: string; channels: Record<string, boolean> }[] }>("/notifications/preferences") });
  const channels = ["email", "sms", "push", "whatsapp"];
  const set = async (event: string, channel: string, enabled: boolean) => { await api("/notifications/preferences", { method: "PUT", body: [{ event, channel, enabled }] }); qc.invalidateQueries({ queryKey: ["prefs"] }); };
  return (
    <Card padded={false}>
      <div className="p-5"><CardHeader title={t("notification_prefs")} subtitle={t("notification_prefs_hint")} /></div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-y border-line text-xs text-muted"><th className="px-5 py-2 text-start">{t("event")}</th>{channels.map((c) => <th key={c} className="px-3 py-2">{t(`channels.${c}`)}{!q.data?.channels[c] && <span className="block text-[10px] text-warning">{t("not_configured")}</span>}</th>)}</tr></thead>
          <tbody>{q.data?.events.map((e) => <tr key={e.event} className="border-b border-line/60"><td className="px-5 py-2.5">{tn(e.event)}</td>{channels.map((c) => <td key={c} className="px-3 py-2.5 text-center"><Switch checked={e.channels[c]} disabled={!q.data?.channels[c]} onChange={(v) => set(e.event, c, v)} /></td>)}</tr>)}</tbody>
        </table>
      </div>
    </Card>
  );
}

function Privacy() {
  const t = useTranslations("settings");
  const f = useFormat();
  const reqs = useQuery({ queryKey: ["privacy-reqs"], queryFn: () => api<{ id: string; kind: string; status: string; created_at: string }[]>("/privacy/requests") });
  const { loading, run } = useApiAction();
  const qc = useQueryClient();
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader title={t("export_data")} subtitle={t("export_hint")} />
        <Button variant="outline" icon={<Download className="h-4 w-4" />} onClick={() => download("/privacy/export", undefined, "wesal-my-data.json")}>{t("download_data")}</Button>
      </Card>
      <Card>
        <CardHeader title={t("delete_account")} subtitle={t("delete_hint")} />
        <Button variant="danger" loading={loading} onClick={async () => { if (await run(() => api("/privacy/requests", { body: { kind: "deletion" } }), { success: t("request_sent") })) qc.invalidateQueries({ queryKey: ["privacy-reqs"] }); }}>{t("request_deletion")}</Button>
        <ul className="mt-4 space-y-1 text-sm">{reqs.data?.map((r) => <li key={r.id} className="flex justify-between"><span>{t(`request_kinds.${r.kind}`)} · {f.date(r.created_at)}</span><span className="text-muted">{t(`request_status.${r.status}`)}</span></li>)}</ul>
      </Card>
    </div>
  );
}

function SettingsInner() {
  const t = useTranslations("settings");
  const sp = useSearchParams();
  const [tab, setTab] = useState<Tab>((sp.get("tab") as Tab) || "profile");
  const { me } = useSession();
  if (!me) return null;
  return (
    <>
      <PageHeader title={t("title")} />
      <div className="mb-5"><Tabs value={tab} onChange={setTab} items={(["profile", "security", "notifications", "privacy"] as Tab[]).map((x) => ({ value: x, label: t(`tabs.${x}`) }))} /></div>
      {tab === "profile" && <Profile />}
      {tab === "security" && <Security />}
      {tab === "notifications" && <NotificationPrefs />}
      {tab === "privacy" && <Privacy />}
    </>
  );
}

export default function Settings() {
  return <Suspense><SettingsInner /></Suspense>;
}
