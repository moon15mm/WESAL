"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Badge, Card, PageHeader } from "@/components/ui/layout";
import { Button, Input } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/list";
import { useApiAction } from "@/lib/useApiForm";

type S = { key: string; value: unknown; is_public: boolean };

export default function PlatformSettings() {
  const t = useTranslations("admin");
  const qc = useQueryClient();
  const q = useApiQuery<S[]>(["platform-settings"], "/admin/settings");
  const [draft, setDraft] = useState<Record<string, string>>({});
  const { loading, run } = useApiAction();
  return (
    <>
      <PageHeader title={t("settings_title")} subtitle={t("settings_subtitle")} />
      <Card padded={false}>
        <ul className="divide-y divide-line">{q.data?.map((s) => {
          const cur = draft[s.key] ?? JSON.stringify(s.value);
          return (
            <li key={s.key} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center">
              <div className="sm:w-64"><p className="ltr font-mono text-sm">{s.key}</p><p className="text-xs text-muted">{t.has(`setting_help.${s.key}`) ? t(`setting_help.${s.key}`) : ""}</p></div>
              <Input dir="ltr" className="flex-1 font-mono text-xs" value={cur} onChange={(e) => setDraft({ ...draft, [s.key]: e.target.value })} />
              {s.is_public && <Badge tone="teal">{t("public")}</Badge>}
              <Button size="sm" loading={loading} disabled={draft[s.key] === undefined} onClick={async () => {
                let value: unknown;
                try { value = JSON.parse(cur); } catch { value = cur; }
                if (await run(() => api(`/admin/settings/${s.key}`, { method: "PUT", body: { value } }), { success: t("saved") })) { setDraft((d) => { const n = { ...d }; delete n[s.key]; return n; }); qc.invalidateQueries({ queryKey: ["platform-settings"] }); }
              }}>{t("save")}</Button>
            </li>
          );
        })}</ul>
      </Card>
    </>
  );
}
