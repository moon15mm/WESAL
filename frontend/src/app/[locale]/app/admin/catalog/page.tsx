"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { DataTable, Pagination, SearchInput, Tabs, type Column } from "@/components/ui/data";
import { Card, PageHeader, StatusBadge } from "@/components/ui/layout";
import { ConfirmDialog, Modal } from "@/components/ui/overlay";
import { Button, Field, Input, Select } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useCategories } from "@/lib/hooks";
import { useList } from "@/lib/list";
import type { Product } from "@/lib/types";
import { useApiAction } from "@/lib/useApiForm";

export default function AdminCatalog() {
  const t = useTranslations("admin");
  const qc = useQueryClient();
  const cats = useCategories();
  const [tab, setTab] = useState<"products" | "categories">("products");
  const [q, setQ] = useState("");
  const products = useList<Product & { offers: number }>(tab === "products" ? "/admin/products" : null, { q });
  const [cat, setCat] = useState<null | { id?: number; slug: string; icon: string; sort_order: number; name: Record<string, string> }>(null);
  const [status, setStatus] = useState<{ p: Product; s: string } | null>(null);
  const { loading, run } = useApiAction();
  const cols: Column<Product & { offers: number }>[] = [
    { key: "n", header: t("product"), cell: (p) => <span><span className="font-medium">{p.name}</span><span className="block text-xs text-muted">{p.category.name}{p.barcode && ` · ${p.barcode}`}</span></span> },
    { key: "o", header: t("offers"), numeric: true, cell: (p) => p.offers },
    { key: "s", header: t("status"), cell: (p) => <StatusBadge status={p.status} /> },
    { key: "a", header: "", cell: (p) => <Select className="h-8 w-36 text-xs" value="" onChange={(e) => e.target.value && setStatus({ p, s: e.target.value })}><option value="">{t("change")}</option>{["active", "archived", "rejected"].filter((s) => s !== p.status).map((s) => <option key={s} value={s}>{t(`pstatus.${s}`)}</option>)}</Select> },
  ];
  return (
    <>
      <PageHeader title={t("catalog_title")} actions={tab === "categories" && <Button icon={<Plus className="h-4 w-4" />} onClick={() => setCat({ slug: "", icon: "package", sort_order: 99, name: { ar: "", en: "", ur: "", hi: "" } })}>{t("add_category")}</Button>} />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:justify-between"><Tabs value={tab} onChange={setTab} items={[{ value: "products", label: t("products") }, { value: "categories", label: t("categories") }]} />{tab === "products" && <SearchInput value={q} onChange={(v) => { setQ(v); products.reset(); }} className="sm:w-72" />}</div>
      {tab === "products" ? (
        <Card padded={false}><DataTable columns={cols} rows={products.data?.items} loading={products.isLoading} rowKey={(p) => p.id} />{products.data && <Pagination page={products.page} pageSize={products.pageSize} total={products.data.total} onPage={products.setPage} />}</Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{cats.data?.map((c) => <Card key={c.id} className="cursor-pointer hover:shadow-[var(--shadow-pop)]" onClick={() => setCat({ id: c.id, slug: c.slug, icon: c.icon || "", sort_order: 0, name: { ar: "", en: "", ur: "", hi: "", ...c.names } })}><p className="font-semibold">{c.name}</p><p className="ltr text-xs text-muted">{c.slug}</p></Card>)}</div>
      )}
      {cat && (
        <Modal open onOpenChange={(v) => !v && setCat(null)} title={cat.id ? t("edit_category") : t("add_category")} footer={<><Button variant="outline" onClick={() => setCat(null)}>{t("cancel")}</Button><Button loading={loading} onClick={async () => {
          const body = { slug: cat.slug, icon: cat.icon || null, sort_order: cat.sort_order, name: cat.name, is_active: true };
          if (await run(() => (cat.id ? api(`/admin/categories/${cat.id}`, { method: "PUT", body }) : api("/admin/categories", { body })), { success: t("saved") })) { setCat(null); qc.invalidateQueries({ queryKey: ["ref", "categories"] }); }
        }}>{t("save")}</Button></>}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="slug">{(id) => <Input id={id} dir="ltr" value={cat.slug} onChange={(e) => setCat({ ...cat, slug: e.target.value })} />}</Field>
            <Field label={t("icon")}>{(id) => <Input id={id} dir="ltr" value={cat.icon} onChange={(e) => setCat({ ...cat, icon: e.target.value })} />}</Field>
            {(["ar", "en", "ur", "hi"] as const).map((l) => <Field key={l} label={`${t("name")} (${l})`}>{(id) => <Input id={id} dir={l === "ar" || l === "ur" ? "rtl" : "ltr"} value={cat.name[l] || ""} onChange={(e) => setCat({ ...cat, name: { ...cat.name, [l]: e.target.value } })} />}</Field>)}
          </div>
        </Modal>
      )}
      <ConfirmDialog open={!!status} onOpenChange={(v) => !v && setStatus(null)} title={t("change_status")} requireReason loading={loading} onConfirm={async (reason) => { if (await run(() => api(`/admin/products/${status!.p.id}/status?status=${status!.s}`, { body: { reason } }))) { setStatus(null); qc.invalidateQueries({ queryKey: ["/admin/products"] }); } }} />
    </>
  );
}
