"use client";

import { FileDown, FileSpreadsheet, FileText } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { BarList, TrendChart } from "@/components/ui/charts";
import { Card, CardHeader, EmptyState, PageHeader, SkeletonRows, Stat } from "@/components/ui/layout";
import { Button, Input } from "@/components/ui/primitives";
import { download } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";

type Section = { key: string; label: string; value: string; money?: boolean };
type KpiDef = { key: string; money?: boolean; percent?: boolean };

export function ReportView({ path, title, kpis, sections }: { path: string; title: string; kpis: KpiDef[]; sections: Section[] }) {
  const t = useTranslations("reports");
  const f = useFormat();
  const today = new Date().toISOString().slice(0, 10);
  const monthAgo = new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10);
  const [from, setFrom] = useState(monthAgo);
  const [to, setTo] = useState(today);
  const query = { date_from: `${from}T00:00:00`, date_to: `${to}T23:59:59` };
  const r = useApiQuery<Record<string, unknown> & { kpis: Record<string, unknown>; series: Record<string, unknown>[] }>(["report", path], path, query);
  const exp = (format: string) => download(path, { ...query, format }, `wesal-report.${format}`);
  return (
    <>
      <PageHeader title={title} subtitle={t("subtitle")} actions={<>
        <Button variant="outline" size="sm" icon={<FileText className="h-4 w-4" />} onClick={() => exp("pdf")}>PDF</Button>
        <Button variant="outline" size="sm" icon={<FileSpreadsheet className="h-4 w-4" />} onClick={() => exp("xlsx")}>Excel</Button>
        <Button variant="outline" size="sm" icon={<FileDown className="h-4 w-4" />} onClick={() => exp("csv")}>CSV</Button>
      </>} />
      <Card className="mb-6 flex flex-wrap items-end gap-3">
        <label className="text-sm"><span className="mb-1 block text-muted">{t("from")}</span><Input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} /></label>
        <label className="text-sm"><span className="mb-1 block text-muted">{t("to")}</span><Input type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} /></label>
      </Card>
      {!r.data ? <SkeletonRows /> : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {kpis.map((k) => {
              const v = r.data!.kpis[k.key];
              return <Stat key={k.key} label={t(`kpi.${k.key}`)} value={k.money ? f.money(v) : k.percent ? f.percent(v) : f.number(v)} />;
            })}
          </div>
          <Card className="mt-6">
            <CardHeader title={t("over_time")} />
            {r.data.series.length ? <TrendChart data={r.data.series} /> : <EmptyState title={t("no_data")} />}
          </Card>
          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            {sections.map((s) => {
              const rows = (r.data![s.key] as Record<string, unknown>[]) || [];
              return (
                <Card key={s.key}>
                  <CardHeader title={t(`section.${s.key}`)} />
                  {rows.length ? <BarList data={rows.slice(0, 10)} label={s.label} value={s.value} money={s.money !== false} /> : <p className="py-6 text-center text-sm text-muted">{t("no_data")}</p>}
                </Card>
              );
            })}
          </div>
        </>
      )}
    </>
  );
}
