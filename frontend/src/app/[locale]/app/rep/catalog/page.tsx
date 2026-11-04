"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { CategoryFilter, OfferCard } from "@/components/app/catalog";
import { Pagination, SearchInput } from "@/components/ui/data";
import { Alert, Card, EmptyState, PageHeader, SkeletonRows } from "@/components/ui/layout";
import { Select } from "@/components/ui/primitives";
import { Link } from "@/i18n/navigation";
import { useList } from "@/lib/list";
import type { Offer } from "@/lib/types";

type Res = { authorizations: { id: string; supplier_id: string; supplier: { name: string } }[] };

export default function RepCatalog() {
  const t = useTranslations("rep");
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [supplier, setSupplier] = useState("");
  const list = useList<Offer>("/rep/catalog", { q, category_id: cat, supplier_id: supplier }, 24);
  const auths = (list.data as unknown as Res | undefined)?.authorizations || [];
  return (
    <>
      <PageHeader title={t("catalog_title")} subtitle={t("catalog_subtitle")} />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row">
        <SearchInput value={q} onChange={(v) => { setQ(v); list.reset(); }} className="flex-1" />
        <Select value={supplier} onChange={(e) => { setSupplier(e.target.value); list.reset(); }} className="sm:w-56"><option value="">{t("all_companies")}</option>{auths.map((a) => <option key={a.id} value={a.supplier_id}>{a.supplier.name}</option>)}</Select>
        <CategoryFilter value={cat} onChange={(v) => { setCat(v); list.reset(); }} />
      </div>
      {list.isLoading ? <SkeletonRows /> : list.data?.items.length ? (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">{list.data.items.map((o) => <OfferCard key={o.id} offer={o} />)}</div>
          <Card padded={false} className="mt-4"><Pagination page={list.page} pageSize={list.pageSize} total={list.data.total} onPage={list.setPage} /></Card>
        </>
      ) : <Card><EmptyState title={t("no_authorized_products")} description={t("no_authorized_hint")} action={<Link href="/app/rep/companies" className="font-semibold text-teal-600">{t("find_companies")} →</Link>} /></Card>}
      <div className="mt-4"><Alert tone="info">{t("prices_note")}</Alert></div>
    </>
  );
}
