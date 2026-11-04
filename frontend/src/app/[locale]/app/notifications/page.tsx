"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Pagination, Tabs } from "@/components/ui/data";
import { Card, EmptyState, PageHeader, SkeletonRows } from "@/components/ui/layout";
import { Button } from "@/components/ui/primitives";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { cx, useFormat } from "@/lib/format";
import { useList } from "@/lib/list";

type N = { id: string; event: string; title: string; body: string; link: string | null; read_at: string | null; created_at: string };

export default function Notifications() {
  const t = useTranslations("notifications");
  const f = useFormat();
  const qc = useQueryClient();
  const [unread, setUnread] = useState(false);
  const list = useList<N>("/notifications", { unread: unread || undefined });
  const read = async (n: N) => { if (!n.read_at) { await api(`/notifications/${n.id}/read`, { method: "POST" }); qc.invalidateQueries({ queryKey: ["notif-count"] }); } };
  return (
    <>
      <PageHeader title={t("title")} actions={<Button variant="outline" icon={<CheckCheck className="h-4 w-4" />} onClick={async () => { await api("/notifications/read-all", { method: "POST" }); qc.invalidateQueries({ queryKey: ["/notifications"] }); qc.invalidateQueries({ queryKey: ["notif-count"] }); }}>{t("read_all")}</Button>} />
      <div className="mb-4"><Tabs value={unread ? "u" : "a"} onChange={(v) => { setUnread(v === "u"); list.reset(); }} items={[{ value: "a", label: t("all") }, { value: "u", label: t("unread"), count: Number(list.data?.unread ?? 0) }]} /></div>
      <Card padded={false}>
        {list.isLoading ? <SkeletonRows /> : list.data?.items.length ? (
          <ul className="divide-y divide-line">
            {list.data.items.map((n) => {
              const content = (
                <div className={cx("flex gap-3 p-4 transition hover:bg-page", !n.read_at && "bg-teal-50/40")}>
                  <span className={cx("mt-1.5 h-2 w-2 shrink-0 rounded-full", n.read_at ? "bg-transparent" : "bg-teal-500")} />
                  <div className="min-w-0 flex-1"><p className="font-medium text-navy-700">{n.title}</p><p className="mt-0.5 text-sm text-muted">{n.body}</p><p className="mt-1 text-xs text-muted">{f.relative(n.created_at)}</p></div>
                </div>
              );
              return <li key={n.id} onClick={() => read(n)}>{n.link ? <Link href={n.link}>{content}</Link> : content}</li>;
            })}
          </ul>
        ) : <EmptyState icon={<Bell className="h-6 w-6" />} title={t("empty")} />}
        {list.data && <Pagination page={list.page} pageSize={list.pageSize} total={list.data.total} onPage={list.setPage} />}
      </Card>
    </>
  );
}
