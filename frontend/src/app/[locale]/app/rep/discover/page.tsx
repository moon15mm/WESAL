"use client";

import { LocateFixed, MapPin, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { AddCustomer } from "@/components/app/crm";
import { SearchInput } from "@/components/ui/data";
import { Badge, Card, EmptyState, PageHeader, SkeletonRows } from "@/components/ui/layout";
import { Button, Select } from "@/components/ui/primitives";
import { useFormat } from "@/lib/format";
import { useCities } from "@/lib/hooks";
import { useApiQuery } from "@/lib/list";

type Store = { retailer_id: string; branch_id: string; name: string; branch_name: string; store_type: string | null; city: { name: string } | null; district: string | null; distance_km: number | null; in_my_crm: boolean; verification_status: string };

export default function Discover() {
  const t = useTranslations("discover");
  const f = useFormat();
  const cities = useCities();
  const [q, setQ] = useState("");
  const [city, setCity] = useState("");
  const [pos, setPos] = useState<{ lat: number; lng: number } | null>(null);
  const [radius, setRadius] = useState("10");
  const [adding, setAdding] = useState<Store | null>(null);
  const data = useApiQuery<Store[]>(["discover"], "/rep/discover", { q, city_id: city || undefined, lat: pos?.lat, lng: pos?.lng, radius_km: pos ? radius : undefined });
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("subtitle")} />
      <Card className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center">
        <SearchInput value={q} onChange={setQ} className="lg:w-64" />
        <Select value={city} onChange={(e) => { setCity(e.target.value); setPos(null); }} className="lg:w-48"><option value="">{t("my_areas")}</option>{cities.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>
        <div className="flex items-center gap-2">
          <Button variant={pos ? "secondary" : "outline"} icon={<LocateFixed className="h-4 w-4" />} onClick={() => navigator.geolocation?.getCurrentPosition((p) => setPos({ lat: p.coords.latitude, lng: p.coords.longitude }))}>{t("near_me")}</Button>
          {pos && <Select value={radius} onChange={(e) => setRadius(e.target.value)} className="w-28">{["2", "5", "10", "25"].map((r) => <option key={r} value={r}>{r} km</option>)}</Select>}
        </div>
        <p className="text-xs text-muted lg:ms-auto lg:max-w-xs">{t("privacy")}</p>
      </Card>
      {data.isLoading ? <SkeletonRows /> : data.data?.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.data.map((s) => (
            <Card key={s.branch_id}>
              <div className="flex items-start justify-between gap-2"><p className="font-semibold text-navy-700">{s.name}</p>{s.in_my_crm && <Badge tone="teal">{t("in_crm")}</Badge>}</div>
              <p className="mt-1 flex items-center gap-1 text-sm text-muted"><MapPin className="h-4 w-4" />{[s.city?.name, s.district].filter(Boolean).join(" · ")}{s.distance_km !== null && ` · ${f.number(s.distance_km)} km`}</p>
              {s.store_type && <p className="mt-1 text-xs text-muted">{t(`types.${s.store_type}`)}</p>}
              {!s.in_my_crm && <Button size="sm" variant="outline" className="mt-4" icon={<Plus className="h-4 w-4" />} onClick={() => setAdding(s)}>{t("add_to_crm")}</Button>}
            </Card>
          ))}
        </div>
      ) : <Card><EmptyState title={t("empty")} description={t("empty_hint")} /></Card>}
      {adding && <AddCustomer side="rep" preset={{ retailer_id: adding.retailer_id, name: adding.name }} onClose={() => setAdding(null)} />}
    </>
  );
}
