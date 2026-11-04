"use client";

import { ChevronLeft, ChevronRight, Search, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { cx, useFormat } from "@/lib/format";
import { EmptyState, SkeletonRows } from "./layout";

export type Column<T> = {
  key: string;
  header: React.ReactNode;
  cell: (row: T) => React.ReactNode;
  className?: string;
  numeric?: boolean;
  hideOnMobile?: boolean;
};

/** Responsive table: full table on desktop, stacked cards on mobile. */
export function DataTable<T>({
  columns,
  rows,
  loading,
  empty,
  onRowClick,
  rowKey,
  mobilePrimary,
}: {
  columns: Column<T>[];
  rows: T[] | undefined;
  loading?: boolean;
  empty?: React.ReactNode;
  onRowClick?: (row: T) => void;
  rowKey: (row: T) => string;
  mobilePrimary?: (row: T) => React.ReactNode;
}) {
  const t = useTranslations("common");
  if (loading) return <SkeletonRows />;
  if (!rows || rows.length === 0) return <>{empty ?? <EmptyState title={t("empty_title")} description={t("empty_description")} />}</>;
  return (
    <>
      <div className="hidden overflow-x-auto md:block scrollbar-thin">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-start text-xs uppercase tracking-wide text-muted">
              {columns.map((c) => (
                <th key={c.key} className={cx("px-4 py-3 text-start font-medium", c.numeric && "text-end", c.className)}>
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={rowKey(r)}
                onClick={onRowClick ? () => onRowClick(r) : undefined}
                className={cx("border-b border-line/60 transition last:border-0", onRowClick && "cursor-pointer hover:bg-navy-50/50")}
              >
                {columns.map((c) => (
                  <td key={c.key} className={cx("px-4 py-3 align-middle", c.numeric && "tabular text-end", c.className)}>
                    {c.cell(r)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="divide-y divide-line/70 md:hidden">
        {rows.map((r) => (
          <li key={rowKey(r)} onClick={onRowClick ? () => onRowClick(r) : undefined} className={cx("px-4 py-3", onRowClick && "active:bg-navy-50")}>
            {mobilePrimary && <div className="mb-2">{mobilePrimary(r)}</div>}
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
              {columns
                .filter((c) => !c.hideOnMobile)
                .map((c) => (
                  <div key={c.key} className="min-w-0">
                    <dt className="text-xs text-muted">{c.header}</dt>
                    <dd className={cx("truncate", c.numeric && "tabular")}>{c.cell(r)}</dd>
                  </div>
                ))}
            </dl>
          </li>
        ))}
      </ul>
    </>
  );
}

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const t = useTranslations("common");
  const f = useFormat();
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;
  return (
    <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm text-muted">
      <span>{t("pagination", { from: f.number((page - 1) * pageSize + 1), to: f.number(Math.min(page * pageSize, total)), total: f.number(total) })}</span>
      <div className="flex items-center gap-1">
        <button className="rounded-md p-1.5 hover:bg-navy-50 disabled:opacity-40" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label={t("previous")}>
          <ChevronLeft className="h-4 w-4 rtl:rotate-180" />
        </button>
        <span className="tabular px-2">{f.number(page)} / {f.number(pages)}</span>
        <button className="rounded-md p-1.5 hover:bg-navy-50 disabled:opacity-40" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label={t("next")}>
          <ChevronRight className="h-4 w-4 rtl:rotate-180" />
        </button>
      </div>
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder, className }: { value: string; onChange: (v: string) => void; placeholder?: string; className?: string }) {
  const t = useTranslations("common");
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  useEffect(() => {
    const h = setTimeout(() => local !== value && onChange(local), 300);
    return () => clearTimeout(h);
  }, [local]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className={cx("relative", className)}>
      <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
      <input
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        placeholder={placeholder || t("search")}
        className="h-10 w-full rounded-md border border-line bg-white ps-9 pe-8 text-sm focus:border-teal-400 focus:shadow-[var(--shadow-focus)] focus:outline-none"
        type="search"
      />
      {local && (
        <button className="absolute end-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted hover:text-ink" onClick={() => { setLocal(""); onChange(""); }} aria-label={t("clear")}>
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: { value: T; label: React.ReactNode; count?: number }[] }) {
  return (
    <div className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1 scrollbar-thin" role="tablist">
      {items.map((it) => (
        <button
          key={it.value}
          role="tab"
          aria-selected={value === it.value}
          onClick={() => onChange(it.value)}
          className={cx(
            "inline-flex shrink-0 items-center gap-2 rounded-full px-3.5 py-1.5 text-sm font-medium transition",
            value === it.value ? "bg-navy-700 text-white shadow-sm" : "bg-white text-muted ring-1 ring-line hover:text-ink",
          )}
        >
          {it.label}
          {it.count !== undefined && <span className={cx("tabular rounded-full px-1.5 text-xs", value === it.value ? "bg-white/20" : "bg-navy-50")}>{it.count}</span>}
        </button>
      ))}
    </div>
  );
}
