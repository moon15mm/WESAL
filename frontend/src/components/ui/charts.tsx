"use client";

import { useLocale } from "next-intl";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useFormat } from "@/lib/format";

const PALETTE = ["#20B99A", "#102B46", "#55D6B0", "#3E6890", "#E5A13B", "#7193B3", "#16A36A", "#D84B4B"];

function TooltipBox({ active, payload, label, money }: { active?: boolean; payload?: { value: number; name: string; color?: string }[]; label?: string; money?: boolean }) {
  const f = useFormat();
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-line bg-white px-3 py-2 text-xs shadow-[var(--shadow-pop)]">
      {label && <p className="mb-1 font-medium text-navy-700">{label}</p>}
      {payload.map((p, i) => (
        <p key={i} className="tabular flex items-center gap-2 text-ink">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color || PALETTE[0] }} />
          {money ? f.money(p.value) : f.number(p.value)}
        </p>
      ))}
    </div>
  );
}

export function TrendChart({ data, x = "period", y = "value", money = true, height = 240 }: { data: Record<string, unknown>[]; x?: string; y?: string; money?: boolean; height?: number }) {
  const f = useFormat();
  const rtl = ["ar", "ur"].includes(useLocale());
  const rows = data.map((d) => ({ ...d, [y]: Number(d[y] ?? 0), _label: f.date(d[x]) }));
  return (
    <div style={{ height }} dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rtl ? [...rows].reverse() : rows} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
          <defs>
            <linearGradient id="wesalArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#20B99A" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#20B99A" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
          <XAxis dataKey="_label" tick={{ fontSize: 11, fill: "#718096" }} tickLine={false} axisLine={false} minTickGap={24} />
          <YAxis orientation={rtl ? "right" : "left"} tick={{ fontSize: 11, fill: "#718096" }} tickLine={false} axisLine={false} width={56}
                 tickFormatter={(v) => f.number(v)} />
          <Tooltip content={<TooltipBox money={money} />} />
          <Area type="monotone" dataKey={y} stroke="#20B99A" strokeWidth={2.5} fill="url(#wesalArea)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function BarList({ data, label, value, money = true }: { data: Record<string, unknown>[]; label: string; value: string; money?: boolean }) {
  const f = useFormat();
  const max = Math.max(1, ...data.map((d) => Number(d[value] || 0)));
  return (
    <ul className="space-y-3">
      {data.map((d, i) => (
        <li key={i}>
          <div className="mb-1 flex items-center justify-between gap-3 text-sm">
            <span className="truncate text-ink">{String(d[label] ?? "—")}</span>
            <span className="tabular shrink-0 font-medium text-navy-700">{money ? f.money(d[value]) : f.number(d[value])}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-navy-50">
            <div className="h-full rounded-full bg-gradient-to-r from-teal-500 to-teal-300 transition-all duration-700" style={{ width: `${(Number(d[value] || 0) / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function Donut({ data, height = 200 }: { data: { name: string; value: number }[]; height?: number }) {
  return (
    <div style={{ height }} dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius="60%" outerRadius="90%" paddingAngle={2} stroke="none">
            {data.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
          </Pie>
          <Tooltip content={<TooltipBox money={false} />} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Bars({ data, x, y, money = true, height = 220 }: { data: Record<string, unknown>[]; x: string; y: string; money?: boolean; height?: number }) {
  const f = useFormat();
  return (
    <div style={{ height }} dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data.map((d) => ({ ...d, [y]: Number(d[y] || 0) }))} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
          <XAxis dataKey={x} tick={{ fontSize: 11, fill: "#718096" }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 11, fill: "#718096" }} tickLine={false} axisLine={false} width={56} tickFormatter={(v) => f.number(v)} />
          <Tooltip content={<TooltipBox money={money} />} cursor={{ fill: "#EEF3F8" }} />
          <Bar dataKey={y} radius={[6, 6, 0, 0]} fill="#102B46" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export const CHART_PALETTE = PALETTE;
