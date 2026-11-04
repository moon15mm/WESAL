"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Building2, Check, Store, UserRound } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Button, Checkbox, Field, Input, Select } from "@/components/ui/primitives";
import { Link, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { cx } from "@/lib/format";
import { useCities } from "@/lib/hooks";
import { useApiAction } from "@/lib/useApiForm";

type Kind = "retailer" | "supplier" | "representative";

function RegisterInner() {
  const t = useTranslations("auth");
  const locale = useLocale();
  const router = useRouter();
  const qc = useQueryClient();
  const initial = useSearchParams().get("type") as Kind | null;
  const [kind, setKind] = useState<Kind | null>(initial && ["retailer", "supplier", "representative"].includes(initial) ? initial : null);
  const cities = useCities();
  const { loading, fields, error, run } = useApiAction();
  const [accept, setAccept] = useState(false);

  const kinds: { k: Kind; icon: typeof Store }[] = [
    { k: "retailer", icon: Store },
    { k: "representative", icon: UserRound },
    { k: "supplier", icon: Building2 },
  ];

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const v = (k: string) => (fd.get(k) ? String(fd.get(k)).trim() : null);
    const body = {
      account_type: kind, full_name: v("full_name"), email: v("email"), phone: v("phone"), password: v("password"),
      locale, accept_terms: accept, business_name_ar: v("business_name_ar"), business_name_en: v("business_name_en"),
      cr_number: v("cr_number"), vat_number: v("vat_number"), city_id: v("city_id") ? Number(v("city_id")) : null,
      district: v("district"), store_type: v("store_type"),
    };
    const ok = await run(() => api("/auth/register", { body }), { silent: true });
    if (ok) {
      await qc.invalidateQueries({ queryKey: ["me"] });
      router.replace("/verify");
    }
  }

  if (!kind)
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-navy-700">{t("register_title")}</h1>
          <p className="mt-1 text-sm text-muted">{t("register_choose")}</p>
        </div>
        <div className="space-y-3">
          {kinds.map(({ k, icon: Icon }) => (
            <button key={k} onClick={() => setKind(k)} data-testid={`type-${k}`}
              className="flex w-full items-center gap-4 rounded-xl border border-line p-4 text-start transition hover:border-teal-300 hover:bg-teal-50/40 hover:shadow-[var(--shadow-card)]">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-navy-700 text-white"><Icon className="h-6 w-6" /></span>
              <span>
                <span className="block font-semibold text-navy-700">{t(`type_${k}`)}</span>
                <span className="mt-0.5 block text-sm text-muted">{t(`type_${k}_desc`)}</span>
              </span>
            </button>
          ))}
        </div>
        <p className="text-center text-sm text-muted">{t("have_account")} <Link href="/login" className="font-semibold text-teal-600">{t("login")}</Link></p>
      </div>
    );

  const business = kind !== "representative";
  return (
    <form onSubmit={submit} className="space-y-4" data-testid="register-form">
      <button type="button" onClick={() => setKind(null)} className="text-sm text-teal-600">← {t("change_type")}</button>
      <div>
        <h1 className="text-2xl font-bold text-navy-700">{t(`type_${kind}`)}</h1>
        <p className="mt-1 text-sm text-muted">{t("register_subtitle")}</p>
      </div>
      <Field label={t("full_name")} required error={fields.full_name && t("invalid")}>{(id) => <Input id={id} name="full_name" required minLength={2} autoComplete="name" />}</Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("email")} required={kind === "supplier"} error={fields.email && t(fields.email === "taken" ? "taken" : "invalid")}>
          {(id) => <Input id={id} name="email" type="email" required={kind === "supplier"} autoComplete="email" dir="ltr" />}
        </Field>
        <Field label={t("phone")} required={kind !== "supplier"} hint={t("phone_hint")} error={fields.phone && t(fields.phone === "taken" ? "taken" : "invalid")}>
          {(id) => <Input id={id} name="phone" type="tel" required={kind !== "supplier"} placeholder="05XXXXXXXX" autoComplete="tel" dir="ltr" />}
        </Field>
      </div>
      {business && (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("business_name_ar")} required>{(id) => <Input id={id} name="business_name_ar" required dir="rtl" />}</Field>
            <Field label={t("business_name_en")}>{(id) => <Input id={id} name="business_name_en" dir="ltr" />}</Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("cr_number")} hint={t("cr_hint")} error={fields.cr_number && t("invalid")}>{(id) => <Input id={id} name="cr_number" inputMode="numeric" pattern="\d{10}" dir="ltr" />}</Field>
            <Field label={t("vat_number")} error={fields.vat_number && t("invalid")}>{(id) => <Input id={id} name="vat_number" inputMode="numeric" pattern="3\d{13}3" dir="ltr" />}</Field>
          </div>
        </>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("city")} required>
          {(id) => (
            <Select id={id} name="city_id" required defaultValue="">
              <option value="" disabled>{t("choose")}</option>
              {cities.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          )}
        </Field>
        {kind === "retailer" ? (
          <Field label={t("store_type")}>
            {(id) => (
              <Select id={id} name="store_type" defaultValue="grocery">
                {["grocery", "minimarket", "supermarket", "hypermarket", "pharmacy", "other"].map((s) => <option key={s} value={s}>{t(`store_types.${s}`)}</option>)}
              </Select>
            )}
          </Field>
        ) : (
          <Field label={t("district")}>{(id) => <Input id={id} name="district" />}</Field>
        )}
      </div>
      <Field label={t("password")} required hint={t("password_hint")} error={fields.password && t("weak_password")}>
        {(id) => <Input id={id} name="password" type="password" required minLength={10} autoComplete="new-password" />}
      </Field>
      <Checkbox checked={accept} onChange={(e) => setAccept(e.target.checked)} name="accept_terms" data-testid="accept-terms"
        label={t.rich("accept_terms", {
          terms: (c) => <Link href="/legal/terms" target="_blank" className="font-medium text-teal-600 underline">{c}</Link>,
          privacy: (c) => <Link href="/legal/privacy" target="_blank" className="font-medium text-teal-600 underline">{c}</Link>,
        })} />
      {error && <p className="rounded-md bg-danger/5 px-3 py-2 text-sm text-danger" role="alert">{error}</p>}
      <Button type="submit" loading={loading} disabled={!accept} className={cx("w-full")} size="lg" icon={<Check className="h-4 w-4" />}>{t("create_account")}</Button>
      <p className="text-xs leading-5 text-muted">{t("verification_note")}</p>
    </form>
  );
}

export default function RegisterPage() {
  return <Suspense><RegisterInner /></Suspense>;
}
