"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Alert, Badge, Card, CardHeader, PageHeader } from "@/components/ui/layout";
import { Button, Input, Select, Switch } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/list";
import { useApiAction } from "@/lib/useApiForm";

type Data = { overrides: { id: string; locale: string; key: string; value: string }[]; backend_missing: Record<string, string[]>; backend_keys: number; languages: { code: string; name: string; direction: string; is_enabled: boolean }[] };

export default function Translations() {
  const t = useTranslations("admin");
  const qc = useQueryClient();
  const q = useApiQuery<Data>(["translations"], "/admin/translations");
  const [v, setV] = useState({ locale: "ar", key: "", value: "" });
  const { loading, run } = useApiAction();
  const refresh = () => qc.invalidateQueries({ queryKey: ["translations"] });
  return (
    <>
      <PageHeader title={t("translations_title")} subtitle={t("translations_subtitle")} />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader title={t("languages")} />
          <ul className="space-y-3">{q.data?.languages.map((l) => <li key={l.code} className="flex items-center justify-between"><span>{l.name} <Badge>{l.direction}</Badge></span><Switch checked={l.is_enabled} disabled={l.code === "ar"} onChange={async (x) => { await run(() => api(`/admin/languages/${l.code}?enabled=${x}`, { method: "POST" })); refresh(); }} /></li>)}</ul>
          <div className="mt-4"><Alert tone={Object.values(q.data?.backend_missing || {}).some((x) => x.length) ? "warning" : "success"} title={t("backend_keys", { n: q.data?.backend_keys || 0 })}>{Object.entries(q.data?.backend_missing || {}).map(([l, ks]) => <p key={l}>{l}: {ks.length}</p>)}</Alert></div>
          <p className="mt-3 text-xs text-muted">{t("add_language_hint")}</p>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title={t("overrides")} subtitle={t("overrides_hint")} />
          <div className="mb-4 grid gap-2 sm:grid-cols-[90px_1fr_1fr_auto]">
            <Select value={v.locale} onChange={(e) => setV({ ...v, locale: e.target.value })}>{["ar", "en", "ur", "hi"].map((l) => <option key={l} value={l}>{l}</option>)}</Select>
            <Input dir="ltr" placeholder="marketing.hero_title_1" value={v.key} onChange={(e) => setV({ ...v, key: e.target.value })} />
            <Input placeholder={t("value")} value={v.value} onChange={(e) => setV({ ...v, value: e.target.value })} />
            <Button loading={loading} disabled={!v.key || !v.value} onClick={async () => { if (await run(() => api("/admin/translations", { method: "PUT", body: v }), { success: t("saved") })) { setV({ ...v, key: "", value: "" }); refresh(); } }}>{t("save")}</Button>
          </div>
          <ul className="divide-y divide-line text-sm">{q.data?.overrides.map((o) => <li key={o.id} className="flex items-center justify-between gap-3 py-2"><span className="min-w-0"><Badge>{o.locale}</Badge> <span className="ltr font-mono text-xs">{o.key}</span><span className="block truncate">{o.value}</span></span><button className="p-1 text-muted hover:text-danger" onClick={async () => { await run(() => api(`/admin/translations/${o.id}`, { method: "DELETE" })); refresh(); }} aria-label="delete"><Trash2 className="h-4 w-4" /></button></li>)}</ul>
        </Card>
      </div>
    </>
  );
}
