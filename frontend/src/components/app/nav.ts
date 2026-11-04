import {
  BarChart3,
  Bell,
  Boxes,
  Building2,
  ClipboardCheck,
  ClipboardList,
  Compass,
  FileSignature,
  FileText,
  Gauge,
  Globe2,
  HandCoins,
  Languages,
  LayoutDashboard,
  ListChecks,
  MapPinned,
  Megaphone,
  MessageSquareWarning,
  Package,
  PackageSearch,
  Percent,
  Route,
  ScrollText,
  Settings,
  ShieldCheck,
  ShoppingBag,
  ShoppingCart,
  Sparkles,
  Star,
  Store,
  Tags,
  Target,
  Truck,
  Undo2,
  Users,
  UsersRound,
  Wallet,
} from "lucide-react";
import type { WorkspaceKind } from "@/lib/session";

export type NavItem = { href: string; key: string; icon: typeof Store; perm?: string; mobile?: boolean };
export type NavGroup = { key: string; items: NavItem[] };

export const NAV: Record<WorkspaceKind, NavGroup[]> = {
  store: [
    { key: "main", items: [
      { href: "/app/store", key: "dashboard", icon: LayoutDashboard, mobile: true },
      { href: "/app/store/market", key: "market", icon: Compass, mobile: true },
      { href: "/app/store/cart", key: "cart", icon: ShoppingCart, perm: "retailer.orders.create", mobile: true },
      { href: "/app/store/orders", key: "orders", icon: ShoppingBag, perm: "retailer.orders.view", mobile: true },
      { href: "/app/store/approvals", key: "approvals", icon: ClipboardCheck, perm: "retailer.orders.approve" },
      { href: "/app/store/reorder", key: "reorder", icon: Sparkles, perm: "retailer.orders.view" },
    ] },
    { key: "manage", items: [
      { href: "/app/store/returns", key: "returns", icon: Undo2, perm: "retailer.orders.view" },
      { href: "/app/complaints", key: "complaints", icon: MessageSquareWarning },
      { href: "/app/store/reports", key: "reports", icon: BarChart3, perm: "retailer.reports.view" },
      { href: "/app/store/branches", key: "branches", icon: MapPinned },
      { href: "/app/business/team", key: "team", icon: Users, perm: "retailer.team.manage" },
      { href: "/app/business", key: "business", icon: Store },
    ] },
  ],
  rep: [
    { key: "main", items: [
      { href: "/app/rep", key: "dashboard", icon: Gauge, mobile: true },
      { href: "/app/rep/visits", key: "visits", icon: Route, mobile: true },
      { href: "/app/rep/customers", key: "customers", icon: UsersRound, mobile: true },
      { href: "/app/rep/orders", key: "orders", icon: ShoppingBag, mobile: true },
      { href: "/app/rep/discover", key: "discover", icon: Compass },
      { href: "/app/rep/catalog", key: "catalog", icon: PackageSearch },
      { href: "/app/rep/tasks", key: "tasks", icon: ListChecks },
    ] },
    { key: "business", items: [
      { href: "/app/rep/commissions", key: "commissions", icon: Wallet, mobile: true },
      { href: "/app/rep/authorizations", key: "authorizations", icon: FileSignature },
      { href: "/app/rep/companies", key: "companies", icon: Building2 },
      { href: "/app/rep/reports", key: "reports", icon: BarChart3 },
      { href: "/app/complaints", key: "complaints", icon: MessageSquareWarning },
      { href: "/app/rep/profile", key: "profile", icon: ShieldCheck },
    ] },
  ],
  supplier: [
    { key: "main", items: [
      { href: "/app/supplier", key: "dashboard", icon: LayoutDashboard, mobile: true },
      { href: "/app/supplier/orders", key: "orders", icon: ShoppingBag, perm: "supplier.orders.view", mobile: true },
      { href: "/app/supplier/products", key: "products", icon: Package, mobile: true },
      { href: "/app/supplier/pricing", key: "pricing", icon: Percent },
      { href: "/app/supplier/returns", key: "returns", icon: Undo2, perm: "supplier.orders.view" },
      { href: "/app/supplier/customers", key: "customers", icon: UsersRound, perm: "supplier.customers.view", mobile: true },
    ] },
    { key: "sales_force", items: [
      { href: "/app/supplier/reps", key: "reps", icon: Users },
      { href: "/app/supplier/authorizations", key: "authorizations", icon: FileSignature },
      { href: "/app/supplier/commissions", key: "commissions", icon: HandCoins, perm: "supplier.commissions.view" },
      { href: "/app/supplier/tasks", key: "tasks", icon: Target },
    ] },
    { key: "manage", items: [
      { href: "/app/supplier/reports", key: "reports", icon: BarChart3, perm: "supplier.reports.view" },
      { href: "/app/supplier/coverage", key: "coverage", icon: Truck },
      { href: "/app/complaints", key: "complaints", icon: MessageSquareWarning },
      { href: "/app/business/team", key: "team", icon: Users, perm: "supplier.team.manage" },
      { href: "/app/business", key: "business", icon: Building2 },
    ] },
  ],
  admin: [
    { key: "main", items: [
      { href: "/app/admin", key: "dashboard", icon: Gauge, perm: "admin.dashboard", mobile: true },
      { href: "/app/admin/verification", key: "verification", icon: ShieldCheck, perm: "admin.businesses.verify", mobile: true },
      { href: "/app/admin/users", key: "users", icon: Users, perm: "admin.users.view", mobile: true },
      { href: "/app/admin/orders", key: "orders", icon: ClipboardList, perm: "admin.orders.view" },
      { href: "/app/admin/complaints", key: "complaints", icon: MessageSquareWarning, perm: "admin.complaints.manage", mobile: true },
      { href: "/app/admin/commissions", key: "commissions", icon: Wallet, perm: "admin.commissions.view" },
    ] },
    { key: "content", items: [
      { href: "/app/admin/catalog", key: "catalog", icon: Boxes, perm: "admin.catalog.manage" },
      { href: "/app/admin/ratings", key: "ratings", icon: Star, perm: "admin.ratings.moderate" },
      { href: "/app/admin/subscriptions", key: "subscriptions", icon: Tags, perm: "admin.subscriptions.manage" },
      { href: "/app/admin/ads", key: "ads", icon: Megaphone, perm: "admin.ads.manage" },
      { href: "/app/admin/content", key: "content_pages", icon: FileText, perm: "admin.content.manage" },
      { href: "/app/admin/translations", key: "translations", icon: Languages, perm: "admin.translations.manage" },
    ] },
    { key: "system", items: [
      { href: "/app/admin/settings", key: "settings", icon: Settings, perm: "admin.settings.manage" },
      { href: "/app/admin/audit", key: "audit", icon: ScrollText, perm: "admin.audit.view" },
      { href: "/app/admin/system", key: "system", icon: Globe2, perm: "admin.system.view" },
    ] },
  ],
};

export const COMMON_NAV: NavItem[] = [
  { href: "/app/notifications", key: "notifications", icon: Bell },
  { href: "/app/settings", key: "settings", icon: Settings },
];

export const HOME: Record<WorkspaceKind, string> = { store: "/app/store", rep: "/app/rep", supplier: "/app/supplier", admin: "/app/admin" };
