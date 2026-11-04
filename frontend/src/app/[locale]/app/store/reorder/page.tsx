"use client";

import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Sparkles, Wand2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Badge, Card, CardHeader, EmptyState, PageHeader } from "@/components/ui/layout";
import { Button, Textarea } from "@/components/ui/primitives";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";
import { useApiAction } from "@/lib/useApiForm";

type Line = { input: string; quantity: number; quantity_detected: boolean; unit: "piece" | "carton"; confidence: number; needs_review: boolean;
  match: { offer_id: string; supplier_id: string; name: string; availability: string } | null; alternatives: { offer_id: string; name: string }[] };
type Forecast = { items: { product_id: string; offer_id: string; supplier_id: string; name: string; avg_interval_days: number; last_order: string; predicted_next: string; days_until: number; urgency: string; suggested_pieces: number }[]; method: string };

export default function Reorder() {
  const t = useTranslations("assistant");
  const f = useFormat();
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [lines, setLines] = useState<Line[] | null>(null);
  const [picked, setPicked] = useState<Record<number, boolean>>({});
  const { loading, run } = useApiAction();
  const forecast = useApiQuery<Forecast>(["forecast"], "/ai/reorder-forecast");

  async function parse() {
    const res = await run(() => api<{ lines: Line[] }>("/ai/parse-order", { body: { text } }));
    if (res) { setLines(res.lines); setPicked(Object.fromEntries(res.lines.map((l, i) => [i, !!l.match && !l.needs_review]))); }
  }
  async function addSelected() {
    const chosen = (lines || []).filter((l, i) => picked[i] && l.match);
    for (const l of chosen) await api(`/retailer/carts/${l.match!.supplier_id}/items`, { method: "PUT", body: { offer_id: l.match!.offer_id, unit: l.unit, quantity: l.quantity } }).catch(() => null);
    qc.invalidateQueries({ queryKey: ["carts"] });
    setLines(null); setText("");
  }
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("subtitle")} />
      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader title={t("nl_title")} subtitle={t("nl_hint")} action={<Wand2 className="h-5 w-5 text-teal-500" />} />
          <Textarea rows={5} value={text} onChange={(e) => setText(e.target.value)} placeholder={t("nl_placeholder")} data-testid="nl-order" />
          <div className="mt-3 flex justify-end"><Button onClick={parse} loading={loading} disabled={text.trim().length < 2} icon={<Sparkles className="h-4 w-4" />}>{t("analyze")}</Button></div>
          {lines && (
            <div className="mt-5 space-y-2" data-testid="nl-results">
              {lines.map((l, i) => (
                <label key={i} className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 ${l.needs_review ? "border-warning/40 bg-warning/5" : "border-line"}`}>
                  <input type="checkbox" className="mt-1 accent-teal-500" disabled={!l.match} checked={!!picked[i]} onChange={(e) => setPicked({ ...picked, [i]: e.target.checked })} />
                  <div className="min-w-0 flex-1 text-sm">
                    <p className="text-muted">“{l.input}”</p>
                    {l.match ? <p className="mt-0.5 font-medium text-ink">{f.number(l.quantity)} × {t(`units.${l.unit}`)} — {l.match.name}</p> : <p className="mt-0.5 font-medium text-danger">{t("no_match")}</p>}
                    <div className="mt-1 flex flex-wrap gap-1">
                      <Badge tone={l.confidence >= 0.6 ? "success" : "warning"}>{t("confidence", { n: Math.round(l.confidence * 100) })}</Badge>
                      {!l.quantity_detected && <Badge tone="warning"><AlertTriangle className="h-3 w-3" />{t("qty_assumed")}</Badge>}
                    </div>
                  </div>
                </label>
              ))}
              <p className="text-xs text-muted">{t("proposal_only")}</p>
              <div className="flex justify-end"><Button onClick={addSelected} icon={<CheckCircle2 className="h-4 w-4" />} disabled={!Object.values(picked).some(Boolean)} data-testid="add-parsed">{t("add_to_cart")}</Button></div>
            </div>
          )}
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title={t("forecast_title")} subtitle={t("forecast_method")} />
          {forecast.data?.items.length ? (
            <ul className="space-y-3">
              {forecast.data.items.map((i) => (
                <li key={i.product_id} className="rounded-md border border-line p-3 text-sm">
                  <div className="flex items-center justify-between gap-2"><span className="font-medium">{i.name}</span><Badge tone={i.urgency === "due" ? "danger" : i.urgency === "soon" ? "warning" : "neutral"}>{t(`urgency.${i.urgency}`)}</Badge></div>
                  <p className="mt-1 text-xs text-muted">{t("forecast_line", { days: f.number(i.avg_interval_days), next: f.date(i.predicted_next), qty: f.number(i.suggested_pieces) })}</p>
                </li>
              ))}
            </ul>
          ) : <EmptyState title={t("forecast_empty")} description={t("forecast_empty_hint")} />}
          <Link href="/app/store/cart" className="mt-4 inline-block text-sm font-medium text-teal-600">{t("go_cart")} →</Link>
        </Card>
      </div>
    </>
  );
}
