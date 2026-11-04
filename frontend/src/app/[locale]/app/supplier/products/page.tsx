"use client";

import { useQueryClient } from "@tanstack/react-query";
import { FileUp, ImagePlus, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { CategoryFilter, ProductImage } from "@/components/app/catalog";
import { DataTable, Pagination, SearchInput, type Column } from "@/components/ui/data";
import { Alert, Badge, Card, PageHeader, StatusBadge } from "@/components/ui/layout";
import { Modal } from "@/components/ui/overlay";
import { Button, Checkbox, Field, Input, Select, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useCategories } from "@/lib/hooks";
import { useApiQuery, useList } from "@/lib/list";
import { useSession } from "@/lib/session";
import type { Offer } from "@/lib/types";
import { useApiAction } from "@/lib/useApiForm";

const AVAIL = ["in_stock", "low_stock", "out_of_stock", "discontinued"];
type Brand = { id: string; name_ar: string; name_en: string };

function blank() {
  return { name_ar: "", name_en: "", name_ur: "", name_hi: "", description_ar: "", description_en: "", brand_id: "", category_id: "", barcode: "", package_size: "",
    sku: "", unit_price: "", carton_price: "", pieces_per_carton: "12", min_order_qty: "1", availability: "in_stock", stock_qty: "", sell_by_piece: true, sell_by_carton: true, is_active: true };
}

export default function SupplierProducts() {
  const t = useTranslations("products");
  const f = useFormat();
  const qc = useQueryClient();
  const { can } = useSession();
  const cats = useCategories();
  const brands = useApiQuery<Brand[]>(["brands"], "/catalog/brands");
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [avail, setAvail] = useState("");
  const list = useList<Offer>("/supplier/products", { q, category_id: cat, availability: avail });
  const [edit, setEdit] = useState<(ReturnType<typeof blank> & { id?: string; owned?: boolean }) | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importRes, setImportRes] = useState<{ created: number; updated: number; errors: { row: number; error: string }[] } | null>(null);
  const [csv, setCsv] = useState<File | null>(null);
  const [brandName, setBrandName] = useState({ ar: "", en: "" });
  const { loading, run } = useApiAction();
  const refresh = () => qc.invalidateQueries({ queryKey: ["/supplier/products"] });
  const canCatalog = can("supplier.catalog.manage");

  function open(o?: Offer) {
    if (!o) return setEdit(blank());
    setEdit({ ...blank(), id: o.id, owned: true, name_ar: o.product.name_ar, name_en: o.product.name_en, description_ar: o.product.description_ar || "", description_en: o.product.description_en || "",
      brand_id: o.product.brand?.id || "", category_id: String(o.product.category.id), barcode: o.product.barcode || "", package_size: o.product.package_size || "", sku: o.sku || "",
      unit_price: o.unit_price, carton_price: o.carton_price || "", pieces_per_carton: String(o.pieces_per_carton), min_order_qty: String(o.min_order_qty), availability: o.availability,
      stock_qty: o.stock_qty === null ? "" : String(o.stock_qty), sell_by_piece: o.sell_by_piece, sell_by_carton: o.sell_by_carton, is_active: o.is_active });
  }
  async function save() {
    if (!edit) return;
    const offer = { sku: edit.sku || null, unit_price: edit.unit_price, carton_price: edit.carton_price || null, pieces_per_carton: Number(edit.pieces_per_carton), min_order_qty: Number(edit.min_order_qty),
      availability: edit.availability, stock_qty: edit.stock_qty === "" ? null : Number(edit.stock_qty), sell_by_piece: edit.sell_by_piece, sell_by_carton: edit.sell_by_carton };
    const product = { name_ar: edit.name_ar, name_en: edit.name_en, name_ur: edit.name_ur || null, name_hi: edit.name_hi || null, description_ar: edit.description_ar || null, description_en: edit.description_en || null,
      brand_id: edit.brand_id || null, category_id: Number(edit.category_id), barcode: edit.barcode || null, package_size: edit.package_size || null };
    const ok = await run(() => (edit.id ? api(`/supplier/products/${edit.id}`, { method: "PATCH", body: { ...offer, is_active: edit.is_active, ...(canCatalog ? { product } : {}) } }) : api("/supplier/products", { body: { ...offer, product } })), { success: t("saved") });
    if (ok) { setEdit(null); refresh(); }
  }
  async function quickStock(o: Offer, availability: string) {
    if (await run(() => api("/supplier/products/stock", { body: [{ offer_id: o.id, availability, stock_qty: o.stock_qty }] }), { success: t("saved") })) refresh();
  }
  async function uploadImage(o: Offer, file: File) {
    const fd = new FormData(); fd.set("file", file);
    if (await run(() => api(`/supplier/products/${o.id}/image`, { form: fd }), { success: t("image_saved") })) refresh();
  }
  const cols: Column<Offer>[] = [
    { key: "p", header: t("product"), cell: (o) => (
      <div className="flex items-center gap-3">
        <label className="relative cursor-pointer" title={t("upload_image")}>
          <ProductImage src={o.product.image_url} alt={o.product.name} className="h-11 w-11" />
          {canCatalog && <><ImagePlus className="absolute -bottom-1 -end-1 h-4 w-4 rounded bg-white text-teal-600" /><input type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files?.[0] && uploadImage(o, e.target.files[0])} /></>}
        </label>
        <div className="min-w-0"><p className="truncate font-medium text-ink">{o.product.name}</p><p className="truncate text-xs text-muted">{[o.product.category.name, o.product.package_size, o.sku].filter(Boolean).join(" · ")}</p></div>
      </div>
    ) },
    { key: "price", header: t("unit_price"), numeric: true, cell: (o) => f.money(o.unit_price) },
    { key: "carton", header: t("carton_price"), numeric: true, hideOnMobile: true, cell: (o) => (o.carton_price ? f.money(o.carton_price) : "—") },
    { key: "stock", header: t("availability"), cell: (o) => (
      <Select value={o.availability} onChange={(e) => quickStock(o, e.target.value)} className="h-8 w-36 text-xs" onClick={(e) => e.stopPropagation()}>{AVAIL.map((a) => <option key={a} value={a}>{t(`avail.${a}`)}</option>)}</Select>
    ) },
    { key: "active", header: t("state"), hideOnMobile: true, cell: (o) => (o.is_active ? <StatusBadge status="active" /> : <Badge>{t("hidden")}</Badge>) },
    { key: "e", header: "", cell: (o) => <Button size="sm" variant="ghost" onClick={() => open(o)}>{t("edit")}</Button> },
  ];
  const E = edit;
  const set = (k: string, v: unknown) => setEdit((x) => (x ? { ...x, [k]: v } : x));
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("subtitle")} actions={canCatalog && <>
        <Button variant="outline" icon={<FileUp className="h-4 w-4" />} onClick={() => setImportOpen(true)}>{t("import")}</Button>
        <Button icon={<Plus className="h-4 w-4" />} onClick={() => open()} data-testid="add-product">{t("add")}</Button>
      </>} />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row">
        <SearchInput value={q} onChange={(v) => { setQ(v); list.reset(); }} className="flex-1" />
        <CategoryFilter value={cat} onChange={(v) => { setCat(v); list.reset(); }} />
        <Select value={avail} onChange={(e) => { setAvail(e.target.value); list.reset(); }} className="sm:w-44"><option value="">{t("all_availability")}</option>{AVAIL.map((a) => <option key={a} value={a}>{t(`avail.${a}`)}</option>)}</Select>
      </div>
      <Card padded={false}>
        <DataTable columns={cols} rows={list.data?.items} loading={list.isLoading} rowKey={(o) => o.id} />
        {list.data && <Pagination page={list.page} pageSize={list.pageSize} total={list.data.total} onPage={list.setPage} />}
      </Card>
      {E && (
        <Modal open onOpenChange={(v) => !v && setEdit(null)} size="xl" title={E.id ? t("edit") : t("add")} description={!E.id ? t("barcode_hint") : undefined}
          footer={<><Button variant="outline" onClick={() => setEdit(null)}>{t("cancel")}</Button><Button loading={loading} onClick={save} disabled={!E.name_ar || !E.name_en || !E.category_id || !E.unit_price} data-testid="save-product">{t("save")}</Button></>}>
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="space-y-3">
              <p className="text-sm font-semibold text-navy-700">{t("identity")}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={t("name_ar")} required>{(id) => <Input id={id} dir="rtl" value={E.name_ar} onChange={(e) => set("name_ar", e.target.value)} />}</Field>
                <Field label={t("name_en")} required>{(id) => <Input id={id} dir="ltr" value={E.name_en} onChange={(e) => set("name_en", e.target.value)} />}</Field>
                <Field label={t("name_ur")}>{(id) => <Input id={id} dir="rtl" value={E.name_ur} onChange={(e) => set("name_ur", e.target.value)} />}</Field>
                <Field label={t("name_hi")}>{(id) => <Input id={id} value={E.name_hi} onChange={(e) => set("name_hi", e.target.value)} />}</Field>
                <Field label={t("category")} required>{(id) => <Select id={id} value={E.category_id} onChange={(e) => set("category_id", e.target.value)}><option value="">—</option>{cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>}</Field>
                <Field label={t("brand")}>{(id) => <Select id={id} value={E.brand_id} onChange={(e) => set("brand_id", e.target.value)}><option value="">—</option>{brands.data?.map((b) => <option key={b.id} value={b.id}>{b.name_ar} / {b.name_en}</option>)}</Select>}</Field>
                <Field label={t("barcode")}>{(id) => <Input id={id} dir="ltr" inputMode="numeric" value={E.barcode} onChange={(e) => set("barcode", e.target.value)} />}</Field>
                <Field label={t("package_size")}>{(id) => <Input id={id} value={E.package_size} onChange={(e) => set("package_size", e.target.value)} placeholder="330 ml" />}</Field>
              </div>
              <div className="flex gap-2 rounded-md bg-page p-2">
                <Input placeholder={t("new_brand_ar")} value={brandName.ar} onChange={(e) => setBrandName({ ...brandName, ar: e.target.value })} />
                <Input placeholder={t("new_brand_en")} value={brandName.en} onChange={(e) => setBrandName({ ...brandName, en: e.target.value })} dir="ltr" />
                <Button variant="outline" disabled={!brandName.ar || !brandName.en} onClick={async () => { const b = await run(() => api<{ id: string }>("/supplier/brands", { body: { name_ar: brandName.ar, name_en: brandName.en } })); if (b) { await qc.invalidateQueries({ queryKey: ["brands"] }); set("brand_id", b.id); setBrandName({ ar: "", en: "" }); } }}>{t("add_brand")}</Button>
              </div>
              <Field label={t("description_ar")}>{(id) => <Textarea id={id} dir="rtl" value={E.description_ar} onChange={(e) => set("description_ar", e.target.value)} />}</Field>
              <Field label={t("description_en")}>{(id) => <Textarea id={id} dir="ltr" value={E.description_en} onChange={(e) => set("description_en", e.target.value)} />}</Field>
            </div>
            <div className="space-y-3">
              <p className="text-sm font-semibold text-navy-700">{t("commercial")}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={t("unit_price")} required>{(id) => <Input id={id} type="number" min={0} step="0.01" value={E.unit_price} onChange={(e) => set("unit_price", e.target.value)} />}</Field>
                <Field label={t("carton_price")}>{(id) => <Input id={id} type="number" min={0} step="0.01" value={E.carton_price} onChange={(e) => set("carton_price", e.target.value)} />}</Field>
                <Field label={t("pieces_per_carton")}>{(id) => <Input id={id} type="number" min={1} value={E.pieces_per_carton} onChange={(e) => set("pieces_per_carton", e.target.value)} />}</Field>
                <Field label={t("moq")} hint={t("moq_hint")}>{(id) => <Input id={id} type="number" min={1} value={E.min_order_qty} onChange={(e) => set("min_order_qty", e.target.value)} />}</Field>
                <Field label={t("sku")}>{(id) => <Input id={id} dir="ltr" value={E.sku} onChange={(e) => set("sku", e.target.value)} />}</Field>
                <Field label={t("stock_qty")}>{(id) => <Input id={id} type="number" min={0} value={E.stock_qty} onChange={(e) => set("stock_qty", e.target.value)} />}</Field>
                <Field label={t("availability")}>{(id) => <Select id={id} value={E.availability} onChange={(e) => set("availability", e.target.value)}>{AVAIL.map((a) => <option key={a} value={a}>{t(`avail.${a}`)}</option>)}</Select>}</Field>
              </div>
              <div className="flex flex-wrap gap-4">
                <Checkbox checked={E.sell_by_piece} onChange={(e) => set("sell_by_piece", e.target.checked)} label={t("sell_by_piece")} />
                <Checkbox checked={E.sell_by_carton} onChange={(e) => set("sell_by_carton", e.target.checked)} label={t("sell_by_carton")} />
                {E.id && <Checkbox checked={E.is_active} onChange={(e) => set("is_active", e.target.checked)} label={t("visible")} />}
              </div>
            </div>
          </div>
        </Modal>
      )}
      <Modal open={importOpen} onOpenChange={(v) => { setImportOpen(v); setImportRes(null); }} title={t("import")} description={t("import_hint")}
        footer={<><Button variant="outline" onClick={() => setImportOpen(false)}>{t("close")}</Button><Button loading={loading} disabled={!csv} onClick={async () => {
          const fd = new FormData(); fd.set("file", csv!);
          const r = await run(() => api<{ created: number; updated: number; errors: { row: number; error: string }[] }>("/supplier/products/import", { form: fd }));
          if (r) { setImportRes(r); refresh(); }
        }}>{t("upload")}</Button></>}>
        <code className="ltr block overflow-x-auto rounded bg-page p-2 text-xs">name_ar,name_en,category_slug,brand_en,barcode,package_size,pieces_per_carton,sku,unit_price,carton_price,min_order_qty,availability</code>
        <Input className="mt-3" type="file" accept=".csv,text/csv" onChange={(e) => setCsv(e.target.files?.[0] || null)} />
        {importRes && <div className="mt-3"><Alert tone={importRes.errors.length ? "warning" : "success"} title={t("import_result", { created: importRes.created, updated: importRes.updated, errors: importRes.errors.length })}>{importRes.errors.slice(0, 10).map((e) => <p key={e.row}>#{e.row}: {e.error}</p>)}</Alert></div>}
      </Modal>
    </>
  );
}
