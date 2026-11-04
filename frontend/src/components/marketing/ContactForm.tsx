"use client";

import { CheckCircle2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button, Field, Input, Select, Textarea } from "@/components/ui/primitives";
import { ApiError, api } from "@/lib/api";

export function ContactForm() {
  const t = useTranslations("marketing");
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setState("sending");
    setError(null);
    try {
      await api("/public/contact", {
        body: {
          name: fd.get("name"),
          email: fd.get("email") || null,
          phone: fd.get("phone") || null,
          audience: fd.get("audience") || null,
          message: fd.get("message"),
          website: fd.get("website") || null,
        },
      });
      setState("sent");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("contact_error"));
      setState("idle");
    }
  }

  if (state === "sent")
    return (
      <div className="flex items-center gap-3 rounded-xl border border-success/30 bg-success/5 p-6 text-success">
        <CheckCircle2 className="h-6 w-6" /> {t("contact_sent")}
      </div>
    );

  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl border border-line bg-page p-6">
      <Field label={t("contact_name")} required>{(id) => <Input id={id} name="name" required minLength={2} />}</Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("contact_email")}>{(id) => <Input id={id} name="email" type="email" />}</Field>
        <Field label={t("contact_phone")}>{(id) => <Input id={id} name="phone" type="tel" dir="ltr" />}</Field>
      </div>
      <Field label={t("contact_audience")}>
        {(id) => (
          <Select id={id} name="audience" defaultValue="">
            <option value="">—</option>
            <option value="retailer">{t("nav_stores")}</option>
            <option value="representative">{t("nav_reps")}</option>
            <option value="supplier">{t("nav_suppliers")}</option>
            <option value="other">{t("contact_other")}</option>
          </Select>
        )}
      </Field>
      <Field label={t("contact_message")} required>{(id) => <Textarea id={id} name="message" required minLength={10} rows={4} />}</Field>
      <input type="text" name="website" tabIndex={-1} autoComplete="off" className="hidden" aria-hidden />
      {error && <p className="text-sm text-danger">{error}</p>}
      <Button type="submit" loading={state === "sending"} className="w-full">{t("contact_send")}</Button>
    </form>
  );
}
