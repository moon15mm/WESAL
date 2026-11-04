"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Building2, Check, ChevronDown, LogOut, Menu, Settings, Shield, Store, UserRound, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { Suspense, useEffect, useState } from "react";
import { Logo, LogoMark } from "@/components/brand/Logo";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { Dropdown } from "@/components/ui/overlay";
import { Spinner } from "@/components/ui/primitives";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { cx } from "@/lib/format";
import { type Workspace, useSession } from "@/lib/session";
import { COMMON_NAV, HOME, NAV, type NavItem } from "./nav";

const WS_ICON = { store: Store, supplier: Building2, rep: UserRound, admin: Shield } as const;

function useNav() {
  const { workspace, can } = useSession();
  if (!workspace) return [];
  return NAV[workspace.kind]
    .map((g) => ({ ...g, items: g.items.filter((i) => !i.perm || can(i.perm)) }))
    .filter((g) => g.items.length);
}

function isActive(pathname: string, href: string) {
  const home = Object.values(HOME).includes(href);
  return home ? pathname === href : pathname === href || pathname.startsWith(href + "/");
}

function WorkspaceSwitcher() {
  const t = useTranslations("app");
  const { workspaces, workspace, setWorkspace } = useSession();
  const router = useRouter();
  if (!workspace) return null;
  const Icon = WS_ICON[workspace.kind];
  const select = (w: Workspace) => {
    setWorkspace(w);
    router.push(HOME[w.kind]);
  };
  const button = (
    <button className="flex w-full items-center gap-3 rounded-lg border border-line bg-white p-2.5 text-start transition hover:border-teal-200" data-testid="workspace-switcher">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-navy-700 text-white"><Icon className="h-4.5 w-4.5" /></span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-navy-700">{workspace.kind === "admin" ? t("ws.admin") : workspace.label}</span>
        <span className="block truncate text-xs text-muted">{t(`ws.${workspace.kind}`)}</span>
      </span>
      {workspaces.length > 1 && <ChevronDown className="h-4 w-4 text-muted" />}
    </button>
  );
  if (workspaces.length < 2) return button;
  return (
    <Dropdown
      align="start"
      trigger={button}
      items={workspaces.map((w) => {
        const I = WS_ICON[w.kind];
        const current = w.kind === workspace.kind && w.businessId === workspace.businessId;
        return {
          label: (
            <span className="flex w-full items-center justify-between gap-6">
              <span>
                <span className="block font-medium">{w.kind === "admin" ? t("ws.admin") : w.label}</span>
                <span className="block text-xs text-muted">{t(`ws.${w.kind}`)}</span>
              </span>
              {current && <Check className="h-4 w-4 text-teal-500" />}
            </span>
          ),
          icon: <I className="h-4 w-4 text-navy-400" />,
          onSelect: () => select(w),
        };
      })}
    />
  );
}

function NavLink({ item, onClick }: { item: NavItem; onClick?: () => void }) {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const active = isActive(pathname, item.href);
  return (
    <Link
      href={item.href}
      onClick={onClick}
      className={cx(
        "group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition",
        active ? "bg-navy-700 text-white shadow-sm" : "text-ink/80 hover:bg-white hover:text-navy-700",
      )}
    >
      <item.icon className={cx("h-[18px] w-[18px] shrink-0", active ? "text-teal-300" : "text-navy-300 group-hover:text-teal-500")} />
      {t(item.key)}
    </Link>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const tn = useTranslations("nav");
  const groups = useNav();
  return (
    <div className="flex h-full flex-col gap-5 overflow-y-auto p-4 scrollbar-thin">
      <Link href="/app" className="px-1" onClick={onNavigate}><Logo size={32} /></Link>
      <WorkspaceSwitcher />
      <nav className="flex-1 space-y-5">
        {groups.map((g) => (
          <div key={g.key}>
            <p className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-wider text-muted/80">{tn(`group.${g.key}`)}</p>
            <div className="space-y-0.5">{g.items.map((i) => <NavLink key={i.href} item={i} onClick={onNavigate} />)}</div>
          </div>
        ))}
        <div className="space-y-0.5 border-t border-line pt-4">{COMMON_NAV.map((i) => <NavLink key={i.href} item={i} onClick={onNavigate} />)}</div>
      </nav>
    </div>
  );
}

function NotificationsBell() {
  const { data } = useQuery({ queryKey: ["notif-count"], queryFn: () => api<{ unread: number }>("/notifications/unread-count"), refetchInterval: 45_000 });
  const tn = useTranslations("nav");
  const n = data?.unread || 0;
  return (
    <Link href="/app/notifications" className="relative rounded-md p-2 text-ink hover:bg-navy-50" aria-label={tn("notifications")} data-testid="bell">
      <Bell className="h-5 w-5" />
      {n > 0 && <span className="tabular absolute -top-0.5 end-0 flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-bold text-white">{n > 99 ? "99+" : n}</span>}
    </Link>
  );
}

function UserMenu() {
  const t = useTranslations("app");
  const { me } = useSession();
  const router = useRouter();
  const qc = useQueryClient();
  if (!me) return null;
  const initials = me.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("");
  return (
    <Dropdown
      trigger={
        <button className="flex items-center gap-2 rounded-full p-0.5 ps-0.5 hover:bg-navy-50" data-testid="user-menu">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-teal-500 to-navy-600 text-xs font-bold text-white">{initials}</span>
        </button>
      }
      items={[
        { label: <span><span className="block font-medium">{me.full_name}</span><span className="ltr block text-xs text-muted">{me.email || me.phone}</span></span>, onSelect: () => router.push("/app/settings") },
        "sep",
        { label: t("settings"), icon: <Settings className="h-4 w-4" />, onSelect: () => router.push("/app/settings") },
        {
          label: t("logout"), icon: <LogOut className="h-4 w-4" />, danger: true,
          onSelect: async () => {
            try { await api("/auth/logout", { method: "POST" }); } catch { /* already gone */ }
            qc.clear();
            router.replace("/login");
          },
        },
      ]}
    />
  );
}

function BottomNav() {
  const t = useTranslations("nav");
  const groups = useNav();
  const pathname = usePathname();
  const items = groups.flatMap((g) => g.items).filter((i) => i.mobile).slice(0, 5);
  if (!items.length) return null;
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden" data-testid="bottom-nav">
      <div className="grid" style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}>
        {items.map((i) => {
          const active = isActive(pathname, i.href);
          return (
            <Link key={i.href} href={i.href} className={cx("flex flex-col items-center gap-1 py-2 text-[11px] font-medium", active ? "text-teal-600" : "text-muted")}>
              <i.icon className={cx("h-5 w-5", active && "stroke-[2.4]")} />
              <span className="max-w-full truncate px-1">{t(i.key)}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

function VerificationBanner() {
  const t = useTranslations("app");
  const { me, workspace, membership } = useSession();
  if (!me) return null;
  const items: { key: string; href: string }[] = [];
  if (!me.email_verified && me.email) items.push({ key: "verify_email", href: "/verify" });
  if (!me.phone_verified && me.phone) items.push({ key: "verify_phone", href: "/verify" });
  if (membership && ["unverified", "rejected"].includes(membership.verification_status)) items.push({ key: "verify_business", href: "/app/business" });
  if (membership && membership.verification_status === "pending") items.push({ key: "business_pending", href: "/app/business" });
  if (workspace?.kind === "rep" && me.representative && me.representative.verification_status !== "verified")
    items.push({ key: me.representative.verification_status === "pending" ? "rep_pending" : "verify_rep", href: "/app/rep/profile" });
  if (workspace?.kind === "admin" && me.mfa_required_for_admin && !me.mfa_enabled) items.push({ key: "enable_mfa", href: "/app/settings?tab=security" });
  if (!items.length) return null;
  return (
    <div className="space-y-2 px-4 pt-4 sm:px-6 lg:px-8">
      {items.map((i) => (
        <Link key={i.key} href={i.href} className="flex items-center justify-between gap-3 rounded-md border border-warning/30 bg-warning/10 px-4 py-2.5 text-sm text-[#8a5c19] transition hover:bg-warning/15">
          <span>{t(`banner.${i.key}`)}</span>
          <span className="shrink-0 font-semibold">{t("banner.action")} →</span>
        </Link>
      ))}
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { me, loading, workspace } = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!loading && me === null) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    if (me?.mfa_pending) router.replace("/login");
  }, [loading, me, router, pathname]);

  if (loading || !me) return <div className="flex min-h-screen items-center justify-center"><LogoMark size={48} className="animate-pulse" /></div>;

  if (!workspace)
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <NoWorkspace />
      </div>
    );

  return (
    <div className="min-h-screen lg:ps-72">
      <aside className="fixed inset-y-0 start-0 z-40 hidden w-72 border-e border-line bg-page lg:block"><Sidebar /></aside>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-navy-900/40 animate-fade-in" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 start-0 w-[86%] max-w-xs bg-page shadow-2xl animate-slide-up">
            <button className="absolute end-3 top-4 rounded-md p-1.5 text-muted hover:bg-white" onClick={() => setOpen(false)} aria-label="close"><X className="h-5 w-5" /></button>
            <Sidebar onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-line bg-white/90 px-4 backdrop-blur sm:px-6 lg:px-8">
        <div className="flex items-center gap-2">
          <button className="rounded-md p-2 hover:bg-navy-50 lg:hidden" onClick={() => setOpen(true)} aria-label="menu" data-testid="open-menu"><Menu className="h-5 w-5" /></button>
          <Link href="/app" className="lg:hidden"><LogoMark size={30} /></Link>
        </div>
        <div className="flex items-center gap-1">
          <Suspense><LanguageSwitcher compact /></Suspense>
          <NotificationsBell />
          <UserMenu />
        </div>
      </header>
      <VerificationBanner />
      <main className="mx-auto max-w-7xl px-4 pb-28 pt-6 sm:px-6 lg:px-8 lg:pb-12">{children}</main>
      <BottomNav />
    </div>
  );
}

function NoWorkspace() {
  const t = useTranslations("app");
  return (
    <div className="max-w-md text-center">
      <LogoMark size={56} className="mx-auto" />
      <h1 className="mt-4 text-xl font-bold text-navy-700">{t("no_workspace_title")}</h1>
      <p className="mt-2 text-sm text-muted">{t("no_workspace_text")}</p>
      <div className="mt-4 flex justify-center"><Spinner className="hidden" /></div>
      <Link href="/app/settings" className="mt-4 inline-block font-semibold text-teal-600">{t("settings")}</Link>
    </div>
  );
}
