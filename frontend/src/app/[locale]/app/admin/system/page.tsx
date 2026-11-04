"use client";

import { Activity, Database, HardDrive, Mail, Server } from "lucide-react";
import { useTranslations } from "next-intl";
import { Badge, Card, CardHeader, KV, PageHeader, SkeletonRows, Stat } from "@/components/ui/layout";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";

type Sys = { database: { ok: boolean; size_bytes: number }; redis: { ok: boolean }; outbox: Record<string, number>; jobs: Record<string, { last_run: string; success: boolean | null; processed: number; error: string | null }>; storage: { total: number; used: number; free: number }; channels: Record<string, boolean>; ai_provider: string; env: string; version: string; failed_deliveries: number };
const gb = (b: number) => `${(b / 1024 ** 3).toFixed(1)} GB`;

export default function System() {
  const t = useTranslations("admin");
  const f = useFormat();
  const q = useApiQuery<Sys>(["system"], "/admin/system");
  if (!q.data) return <SkeletonRows />;
  const s = q.data;
  return (
    <>
      <PageHeader title={t("system_title")} subtitle={`${s.env} · v${s.version}`} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label={t("database")} value={s.database.ok ? "OK" : "ERROR"} icon={<Database className="h-5 w-5" />} hint={`${(s.database.size_bytes / 1024 ** 2).toFixed(1)} MB`} />
        <Stat label="Redis" value={s.redis.ok ? "OK" : t("unavailable")} icon={<Server className="h-5 w-5" />} tone={s.redis.ok ? "teal" : "warning"} />
        <Stat label={t("storage")} value={gb(s.storage.free)} icon={<HardDrive className="h-5 w-5" />} hint={t("free_of", { total: gb(s.storage.total) })} />
        <Stat label={t("failed_deliveries")} value={f.number(s.failed_deliveries)} icon={<Mail className="h-5 w-5" />} tone={s.failed_deliveries ? "danger" : "navy"} />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title={t("channels")} />
          <div className="flex flex-wrap gap-2">{Object.entries(s.channels).map(([c, ok]) => <Badge key={c} tone={ok ? "success" : "neutral"}>{c}: {ok ? t("configured") : t("not_configured")}</Badge>)}<Badge tone="teal">AI: {s.ai_provider}</Badge></div>
          <div className="mt-4"><KV items={Object.entries(s.outbox).map(([k, v]) => [k, f.number(v)])} /></div>
        </Card>
        <Card>
          <CardHeader title={t("jobs")} action={<Activity className="h-5 w-5 text-teal-500" />} />
          <ul className="space-y-2 text-sm">{Object.entries(s.jobs).map(([name, j]) => <li key={name} className="flex items-center justify-between gap-2"><span className="ltr font-mono text-xs">{name}</span><span className="flex items-center gap-2 text-xs text-muted">{f.datetime(j.last_run)}<Badge tone={j.success ? "success" : "danger"}>{j.success ? "ok" : "fail"}</Badge></span></li>)}</ul>
          {!Object.keys(s.jobs).length && <p className="text-sm text-muted">{t("no_jobs")}</p>}
        </Card>
      </div>
    </>
  );
}
