"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { DataTable } from "@/components/ui/data";
import { Card, PageHeader } from "@/components/ui/layout";
import { Modal } from "@/components/ui/overlay";
import { Button, Field, Input, Select, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";
import { useApiAction } from "@/lib/useApiForm";

type P = { id: string; slug: string; locale: string; title: string; version: string; is_published: boolean; updated_at: string };

export default function Content() {
  const t = useTranslations("admin");
  const f = useFormat();
  const qc = useQueryClient();
  const pages = useApiQuery<P[]>(["pages"], "/admin/pages");
  const [edit, setEdit] = useState<{ slug: string; locale: string; title: string; body: string; version: string } | null>(null);
  const { loading, run } = useApiAction();
  const openPage = async (p: P) => {
    const res = await fetch(`/api/v1/public/pages/${p.slug}`, { headers: { "x-locale": p.locale } });
    const d = await res.json();
    setEdit({ slug: p.slug, locale: p.locale, title: d.title, body: d.locale === p.locale ? d.body : "", version: p.version });
  };
  return (
    <>
      <PageHeader title={t("content_title")} subtitle={t("content_subtitle")} actions={<Button onClick={() => setEdit({ slug: "", locale: "ar", title: "", body: "", version: "1.0" })}>{t("new_page")}</Button>} />
      <Card padded={false}><DataTable rows={pages.data} loading={pages.isLoading} rowKey={(p) => p.id} onRowClick={openPage} columns={[
        { key: "s", header: "slug", cell: (p) => <span className="ltr">{p.slug}</span> }, { key: "l", header: t("language"), cell: (p) => p.locale },
        { key: "t", header: t("page_title"), cell: (p) => p.title }, { key: "v", header: t("version"), cell: (p) => p.version }, { key: "u", header: t("updated"), cell: (p) => f.date(p.updated_at) },
      ]} /></Card>
      {edit && (
        <Modal open onOpenChange={(v) => !v && setEdit(null)} size="xl" title={edit.slug || t("new_page")} footer={<><Button variant="outline" onClick={() => setEdit(null)}>{t("cancel")}</Button><Button loading={loading} onClick={async () => { if (await run(() => api("/admin/pages", { method: "PUT", body: { ...edit, is_published: true } }), { success: t("saved") })) { setEdit(null); qc.invalidateQueries({ queryKey: ["pages"] }); } }}>{t("save")}</Button></>}>
          <div className="grid gap-3 sm:grid-cols-4">
            <Field label="slug">{(id) => <Input id={id} dir="ltr" value={edit.slug} onChange={(e) => setEdit({ ...edit, slug: e.target.value })} />}</Field>
            <Field label={t("language")}>{(id) => <Select id={id} value={edit.locale} onChange={(e) => setEdit({ ...edit, locale: e.target.value })}>{["ar", "en", "ur", "hi"].map((l) => <option key={l} value={l}>{l}</option>)}</Select>}</Field>
            <Field label={t("version")}>{(id) => <Input id={id} value={edit.version} onChange={(e) => setEdit({ ...edit, version: e.target.value })} />}</Field>
            <Field label={t("page_title")}>{(id) => <Input id={id} value={edit.title} onChange={(e) => setEdit({ ...edit, title: e.target.value })} />}</Field>
          </div>
          <Field label={t("body_markdown")} className="mt-3">{(id) => <Textarea id={id} rows={16} dir={["ar", "ur"].includes(edit.locale) ? "rtl" : "ltr"} className="font-mono text-xs" value={edit.body} onChange={(e) => setEdit({ ...edit, body: e.target.value })} />}</Field>
        </Modal>
      )}
    </>
  );
}
