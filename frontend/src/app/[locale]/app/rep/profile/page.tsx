"use client";

import { useQueryClient } from "@tanstack/react-query";
import { FileUp, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Alert, Card, CardHeader, PageHeader, SkeletonRows, StatusBadge } from "@/components/ui/layout";
import { Button, Field, Input, Select, Switch, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useCategories, useCities } from "@/lib/hooks";
import { useApiQuery } from "@/lib/list";
import { useSession } from "@/lib/session";
import { useApiAction } from "@/lib/useApiForm";

type Profile = { display_name: string; headline: string | null; bio: string | null; experience_years: number; skills: string[]; availability: string; public_profile: boolean; verification_status: string; rejection_reason: string | null; freelance_doc_number: string | null; areas: { city_id: number; district: string | null }[]; categories: { id: number }[] };
type Doc = { id: string; doc_type: string; status: string; file_url: string; created_at: string };

export default function RepProfile() {
  const t = useTranslations("rep_profile");
  const qc = useQueryClient();
  const { refresh } = useSession();
  const cities = useCities();
  const cats = useCategories();
  const p = useApiQuery<Profile>(["rep-profile"], "/rep/profile");
  const docs = useApiQuery<Doc[]>(["rep-docs"], "/rep/documents");
  const [v, setV] = useState<Profile | null>(null);
  const [skills, setSkills] = useState("");
  const [docType, setDocType] = useState("national_id");
  const [file, setFile] = useState<File | null>(null);
  const { loading, run } = useApiAction();
  useEffect(() => { if (p.data) { setV(p.data); setSkills(p.data.skills.join("، ")); } }, [p.data]);
  if (!v) return <SkeletonRows />;
  const areaIds = v.areas.map((a) => a.city_id);
  const catIds = v.categories.map((c) => c.id);
  async function save() {
    const body = { display_name: v!.display_name, headline: v!.headline, bio: v!.bio, experience_years: Number(v!.experience_years), availability: v!.availability, public_profile: v!.public_profile,
      freelance_doc_number: v!.freelance_doc_number, skills: skills.split(/[,،]/).map((s) => s.trim()).filter(Boolean), areas: v!.areas, category_ids: catIds };
    if (await run(() => api("/rep/profile", { method: "PATCH", body }), { success: t("saved") })) qc.invalidateQueries({ queryKey: ["rep-profile"] });
  }
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("subtitle")} actions={<StatusBadge status={v.verification_status} />} />
      {v.verification_status === "rejected" && <div className="mb-4"><Alert tone="danger" title={t("rejected")}>{v.rejection_reason}</Alert></div>}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("display_name")}>{(id) => <Input id={id} value={v.display_name} onChange={(e) => setV({ ...v, display_name: e.target.value })} />}</Field>
            <Field label={t("headline")}>{(id) => <Input id={id} value={v.headline || ""} onChange={(e) => setV({ ...v, headline: e.target.value })} />}</Field>
            <Field label={t("bio")} className="sm:col-span-2">{(id) => <Textarea id={id} rows={4} value={v.bio || ""} onChange={(e) => setV({ ...v, bio: e.target.value })} />}</Field>
            <Field label={t("experience")}>{(id) => <Input id={id} type="number" min={0} value={v.experience_years} onChange={(e) => setV({ ...v, experience_years: Number(e.target.value) })} />}</Field>
            <Field label={t("availability")}>{(id) => <Select id={id} value={v.availability} onChange={(e) => setV({ ...v, availability: e.target.value })}>{["available", "limited", "unavailable"].map((a) => <option key={a} value={a}>{t(`availability_${a}`)}</option>)}</Select>}</Field>
            <Field label={t("skills")} hint={t("skills_hint")} className="sm:col-span-2">{(id) => <Input id={id} value={skills} onChange={(e) => setSkills(e.target.value)} />}</Field>
            <Field label={t("freelance_doc")}>{(id) => <Input id={id} dir="ltr" value={v.freelance_doc_number || ""} onChange={(e) => setV({ ...v, freelance_doc_number: e.target.value })} />}</Field>
            <div className="flex items-end"><Switch checked={v.public_profile} onChange={(x) => setV({ ...v, public_profile: x })} label={t("public_profile")} /></div>
          </div>
          <div className="mt-6">
            <p className="mb-2 text-sm font-medium">{t("areas")}</p>
            <div className="flex flex-wrap gap-2">{cities.data?.map((c) => <button key={c.id} type="button" onClick={() => setV({ ...v, areas: areaIds.includes(c.id) ? v.areas.filter((a) => a.city_id !== c.id) : [...v.areas, { city_id: c.id, district: null }] })} className={`rounded-full px-3 py-1 text-xs ring-1 ${areaIds.includes(c.id) ? "bg-navy-700 text-white ring-navy-700" : "ring-line"}`}>{c.name}</button>)}</div>
          </div>
          <div className="mt-5">
            <p className="mb-2 text-sm font-medium">{t("categories")}</p>
            <div className="flex flex-wrap gap-2">{cats.data?.map((c) => <button key={c.id} type="button" onClick={() => setV({ ...v, categories: catIds.includes(c.id) ? v.categories.filter((x) => x.id !== c.id) : [...v.categories, { id: c.id }] })} className={`rounded-full px-3 py-1 text-xs ring-1 ${catIds.includes(c.id) ? "bg-teal-500 text-white ring-teal-500" : "ring-line"}`}>{c.name}</button>)}</div>
          </div>
          <div className="mt-6 flex justify-end"><Button loading={loading} onClick={save}>{t("save")}</Button></div>
        </Card>
        <Card>
          <CardHeader title={t("verification")} subtitle={t("verification_hint")} action={<ShieldCheck className="h-5 w-5 text-teal-500" />} />
          <ul className="mb-4 space-y-2 text-sm">{docs.data?.map((d) => <li key={d.id} className="flex items-center justify-between"><a href={d.file_url} target="_blank" className="text-teal-700 underline">{t(`doc_types.${d.doc_type}`)}</a><StatusBadge status={d.status} /></li>)}</ul>
          <div className="space-y-3">
            <Select value={docType} onChange={(e) => setDocType(e.target.value)}>{["national_id", "iqama", "freelance_certificate", "other"].map((d) => <option key={d} value={d}>{t(`doc_types.${d}`)}</option>)}</Select>
            <Input type="file" accept="image/*,application/pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} />
            <Button variant="outline" className="w-full" icon={<FileUp className="h-4 w-4" />} disabled={!file} loading={loading} onClick={async () => {
              const fd = new FormData(); fd.set("doc_type", docType); fd.set("file", file!);
              if (await run(() => api("/rep/documents", { form: fd }), { success: t("uploaded") })) { setFile(null); qc.invalidateQueries({ queryKey: ["rep-docs"] }); }
            }}>{t("upload")}</Button>
            {["unverified", "rejected"].includes(v.verification_status) && <Button className="w-full" loading={loading} onClick={async () => { if (await run(() => api("/rep/verification/submit", { method: "POST" }), { success: t("submitted") })) { qc.invalidateQueries({ queryKey: ["rep-profile"] }); refresh(); } }}>{t("submit_verification")}</Button>}
          </div>
          <p className="mt-4 text-xs text-muted">{t("privacy_note")}</p>
        </Card>
      </div>
    </>
  );
}
