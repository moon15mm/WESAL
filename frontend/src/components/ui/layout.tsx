"use client";

import { ArrowDownRight, ArrowUpRight, Inbox } from "lucide-react";
import { useTranslations } from "next-intl";
import { cx } from "@/lib/format";

export function Card({ className, children, padded = true, ...rest }: React.HTMLAttributes<HTMLDivElement> & { padded?: boolean }) {
  return (
    <div className={cx("rounded-lg border border-line/70 bg-white shadow-[var(--shadow-card)]", padded && "p-5", className)} {...rest}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action, className }: { title: React.ReactNode; subtitle?: React.ReactNode; action?: React.ReactNode; className?: string }) {
  return (
    <div className={cx("mb-4 flex items-start justify-between gap-3", className)}>
      <div className="min-w-0">
        <h3 className="text-base font-semibold text-navy-700">{title}</h3>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions, back }: { title: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; back?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between animate-fade-in">
      <div className="min-w-0">
        {back}
        <h1 className="text-2xl font-bold tracking-tight text-navy-700">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

type Tone = "neutral" | "success" | "warning" | "danger" | "info" | "teal" | "navy";
const tones: Record<Tone, string> = {
  neutral: "bg-navy-50 text-navy-500 ring-navy-100",
  success: "bg-success/10 text-success ring-success/20",
  warning: "bg-warning/10 text-[#a8701f] ring-warning/25",
  danger: "bg-danger/10 text-danger ring-danger/20",
  info: "bg-navy-50 text-navy-400 ring-navy-100",
  teal: "bg-teal-50 text-teal-700 ring-teal-100",
  navy: "bg-navy-700 text-white ring-navy-700",
};

export function Badge({ tone = "neutral", children, className, dot }: { tone?: Tone; children: React.ReactNode; className?: string; dot?: boolean }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset", tones[tone], className)}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

const STATUS_TONES: Record<string, Tone> = {
  // orders
  draft: "neutral", pending_retailer_approval: "warning", new: "info", supplier_review: "info", quoted: "warning",
  awaiting_retailer_approval: "warning", approved: "teal", preparing: "info", ready: "teal", out_for_delivery: "info",
  delivered: "success", completed: "success", rejected: "danger", cancelled: "danger", partially_returned: "warning",
  fully_returned: "danger", disputed: "danger",
  // generic
  active: "success", verified: "success", pending: "warning", unverified: "neutral", suspended: "danger", expired: "neutral",
  sent: "info", pending_rep: "warning", in_stock: "success", low_stock: "warning", out_of_stock: "danger", discontinued: "neutral",
  estimated: "neutral", due: "teal", paid: "success", adjusted: "warning", requested: "warning", received: "info", settled: "success",
  open: "warning", in_review: "info", resolved: "success", closed: "neutral", scheduled: "info", in_progress: "teal", missed: "danger",
  lead: "neutral", prospect: "info", inactive: "neutral", lost: "danger", unpaid: "warning", partially_paid: "warning",
  invited: "info", disabled: "neutral", awaiting_response: "warning", flagged: "warning", hidden: "neutral", published: "success",
};

export function StatusBadge({ status, ns = "status" }: { status: string; ns?: string }) {
  const t = useTranslations(ns);
  return (
    <Badge tone={STATUS_TONES[status] || "neutral"} dot>
      {t.has(status) ? t(status) : status}
    </Badge>
  );
}

export function Stat({ label, value, hint, icon, trend, tone = "navy" }: { label: React.ReactNode; value: React.ReactNode; hint?: React.ReactNode; icon?: React.ReactNode; trend?: number | null; tone?: "navy" | "teal" | "warning" | "danger" }) {
  const toneBg = { navy: "bg-navy-50 text-navy-600", teal: "bg-teal-50 text-teal-600", warning: "bg-warning/10 text-[#a8701f]", danger: "bg-danger/10 text-danger" }[tone];
  return (
    <Card className="group relative overflow-hidden transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-pop)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-muted">{label}</p>
          <p className="tabular mt-1.5 whitespace-nowrap text-lg font-bold leading-tight text-navy-700 sm:text-xl 2xl:text-2xl">{value}</p>
        </div>
        {icon && <div className={cx("flex h-10 w-10 shrink-0 items-center justify-center rounded-md", toneBg)}>{icon}</div>}
      </div>
      {(hint || trend !== undefined) && (
        <div className="mt-3 flex items-center gap-2 text-xs text-muted">
          {trend !== undefined && trend !== null && (
            <span className={cx("inline-flex items-center gap-0.5 font-medium", trend >= 0 ? "text-success" : "text-danger")}>
              {trend >= 0 ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}
              {Math.abs(trend)}%
            </span>
          )}
          {hint}
        </div>
      )}
    </Card>
  );
}

export function EmptyState({ title, description, action, icon }: { title: React.ReactNode; description?: React.ReactNode; action?: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center animate-fade-in">
      <div className="relative mb-4">
        <div className="absolute inset-0 rounded-full bg-teal-100 blur-xl" />
        <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-50 to-white text-teal-600 ring-1 ring-teal-100">
          {icon || <Inbox className="h-6 w-6" />}
        </div>
      </div>
      <h3 className="text-base font-semibold text-navy-700">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton rounded-md", className)} />;
}

export function SkeletonRows({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3 p-4">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="h-9 w-9 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-2/3" />
          </div>
          <Skeleton className="h-6 w-16" />
        </div>
      ))}
    </div>
  );
}

export function KV({ items, className }: { items: [React.ReactNode, React.ReactNode][]; className?: string }) {
  return (
    <dl className={cx("grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2", className)}>
      {items.map(([k, v], i) => (
        <div key={i} className="min-w-0">
          <dt className="text-xs text-muted">{k}</dt>
          <dd className="mt-0.5 break-words text-sm font-medium text-ink">{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Alert({ tone = "info", title, children, action }: { tone?: "info" | "warning" | "danger" | "success"; title?: React.ReactNode; children?: React.ReactNode; action?: React.ReactNode }) {
  const map = { info: "border-navy-100 bg-navy-50 text-navy-600", warning: "border-warning/30 bg-warning/10 text-[#8a5c19]", danger: "border-danger/30 bg-danger/5 text-danger", success: "border-success/30 bg-success/5 text-success" };
  return (
    <div className={cx("flex flex-col gap-3 rounded-md border p-4 text-sm sm:flex-row sm:items-center sm:justify-between", map[tone])}>
      <div>
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cx(!!title && "mt-0.5", "opacity-90")}>{children}</div>}
      </div>
      {action}
    </div>
  );
}
