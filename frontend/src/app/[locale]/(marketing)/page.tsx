import {
  BadgeCheck,
  BarChart3,
  Bell,
  Boxes,
  Building2,
  CheckCircle2,
  ClipboardCheck,
  FileSignature,
  Handshake,
  Languages,
  MapPin,
  PackageCheck,
  Route,
  ShieldCheck,
  ShoppingCart,
  Sparkles,
  Store,
  Truck,
  UserRound,
  Wallet,
} from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { ContactForm } from "@/components/marketing/ContactForm";
import { SiteFooter, SiteHeader } from "@/components/marketing/SiteChrome";
import { Link } from "@/i18n/navigation";

const FAQ_KEYS = ["what", "payments", "delivery", "reps_any_company", "approval", "fees", "data", "languages"];

export default async function Landing({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("marketing");

  const audiences = [
    { id: "stores", icon: Store, color: "from-teal-500 to-teal-300", items: ["stores_b1", "stores_b2", "stores_b3", "stores_b4", "stores_b5"], cta: "/register?type=retailer", ctaKey: "join_store" },
    { id: "reps", icon: UserRound, color: "from-navy-500 to-navy-300", items: ["reps_b1", "reps_b2", "reps_b3", "reps_b4", "reps_b5"], cta: "/register?type=representative", ctaKey: "join_rep" },
    { id: "suppliers", icon: Building2, color: "from-[#E5A13B] to-[#f3c77e]", items: ["suppliers_b1", "suppliers_b2", "suppliers_b3", "suppliers_b4", "suppliers_b5"], cta: "/register?type=supplier", ctaKey: "join_supplier" },
  ] as const;

  const flow = [
    { icon: ShoppingCart, key: "flow_1" },
    { icon: ClipboardCheck, key: "flow_2" },
    { icon: Handshake, key: "flow_3" },
    { icon: Truck, key: "flow_4" },
    { icon: PackageCheck, key: "flow_5" },
  ];

  const features = [
    { icon: FileSignature, key: "feat_authorizations" },
    { icon: Wallet, key: "feat_commissions" },
    { icon: Route, key: "feat_visits" },
    { icon: BarChart3, key: "feat_reports" },
    { icon: Sparkles, key: "feat_ai" },
    { icon: Languages, key: "feat_languages" },
    { icon: Bell, key: "feat_notifications" },
    { icon: ShieldCheck, key: "feat_security" },
  ];

  return (
    <>
      {/* ---------------------------------------------------------------- hero */}
      <section className="relative overflow-hidden bg-navy-700 text-white">
        <div className="bg-grid absolute inset-0" />
        <div className="absolute -top-40 end-[-10%] h-[520px] w-[520px] rounded-full bg-teal-500/25 blur-[120px]" />
        <div className="absolute -bottom-40 start-[-10%] h-[420px] w-[420px] rounded-full bg-navy-400/40 blur-[110px]" />
        <SiteHeader transparent />
        <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-4 pb-20 pt-32 sm:px-6 lg:grid-cols-2 lg:pb-28 lg:pt-40">
          <div className="animate-slide-up">
            <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-teal-200 ring-1 ring-white/15">
              <MapPin className="h-3.5 w-3.5" /> {t("hero_badge")}
            </span>
            <h1 className="mt-5 text-4xl font-bold leading-tight tracking-tight sm:text-5xl lg:text-[3.4rem] lg:leading-[1.15]">
              {t("hero_title_1")} <span className="bg-gradient-to-r from-teal-300 to-teal-500 bg-clip-text text-transparent">{t("hero_title_2")}</span>
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-8 text-navy-100">{t("hero_subtitle")}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/register" className="inline-flex h-12 items-center rounded-md bg-teal-500 px-6 font-semibold text-white shadow-lg shadow-teal-500/25 transition hover:bg-teal-400">
                {t("hero_cta_primary")}
              </Link>
              <a href="#how" className="inline-flex h-12 items-center rounded-md px-6 font-semibold text-white ring-1 ring-white/25 transition hover:bg-white/10">
                {t("hero_cta_secondary")}
              </a>
            </div>
            <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-navy-100">
              {["hero_point_1", "hero_point_2", "hero_point_3"].map((k) => (
                <li key={k} className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-teal-300" />{t(k)}</li>
              ))}
            </ul>
          </div>
          <HeroVisual t={t} />
        </div>
      </section>

      {/* ---------------------------------------------------------------- how */}
      <section id="how" className="scroll-mt-20 py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <SectionTitle eyebrow={t("how_eyebrow")} title={t("how_title")} subtitle={t("how_subtitle")} />
          <div className="mt-12 grid gap-6 md:grid-cols-2">
            {[
              { title: "path_direct_title", steps: ["path_direct_1", "path_direct_2", "path_direct_3", "path_direct_4"], icon: Store },
              { title: "path_rep_title", steps: ["path_rep_1", "path_rep_2", "path_rep_3", "path_rep_4"], icon: UserRound },
            ].map((p) => (
              <div key={p.title} className="rounded-xl border border-line bg-white p-7 shadow-[var(--shadow-card)]">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-teal-50 text-teal-600"><p.icon className="h-5 w-5" /></div>
                  <h3 className="text-lg font-semibold text-navy-700">{t(p.title)}</h3>
                </div>
                <ol className="mt-6 space-y-4">
                  {p.steps.map((s, i) => (
                    <li key={s} className="flex gap-4">
                      <span className="tabular flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-navy-700 text-xs font-bold text-white">{i + 1}</span>
                      <p className="pt-0.5 text-sm leading-6 text-ink">{t(s)}</p>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- audiences */}
      <section className="bg-white py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <SectionTitle eyebrow={t("aud_eyebrow")} title={t("aud_title")} subtitle={t("aud_subtitle")} />
          <div className="mt-12 grid gap-6 lg:grid-cols-3">
            {audiences.map((a) => (
              <div id={a.id} key={a.id} className="group relative flex scroll-mt-24 flex-col overflow-hidden rounded-xl border border-line bg-page p-7 transition hover:-translate-y-1 hover:shadow-[var(--shadow-pop)]">
                <div className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${a.color}`} />
                <div className={`flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${a.color} text-white shadow-md`}><a.icon className="h-6 w-6" /></div>
                <h3 className="mt-5 text-xl font-bold text-navy-700">{t(`${a.id}_title`)}</h3>
                <p className="mt-2 text-sm leading-6 text-muted">{t(`${a.id}_subtitle`)}</p>
                <ul className="mt-5 flex-1 space-y-3">
                  {a.items.map((k) => (
                    <li key={k} className="flex gap-2.5 text-sm leading-6"><BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-teal-500" />{t(k)}</li>
                  ))}
                </ul>
                <Link href={a.cta} className="mt-7 inline-flex h-11 items-center justify-center rounded-md bg-navy-700 px-5 text-sm font-semibold text-white transition group-hover:bg-navy-600">
                  {t(a.ctaKey)}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- order flow */}
      <section className="py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <SectionTitle eyebrow={t("flow_eyebrow")} title={t("flow_title")} subtitle={t("flow_subtitle")} />
          <ol className="relative mt-14 grid gap-6 md:grid-cols-5">
            <div className="absolute inset-x-[10%] top-7 hidden h-0.5 bg-gradient-to-r from-teal-200 via-teal-400 to-teal-200 md:block" />
            {flow.map((s, i) => (
              <li key={s.key} className="relative flex flex-col items-center text-center">
                <div className="relative z-10 flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-teal-600 shadow-[var(--shadow-card)] ring-1 ring-line"><s.icon className="h-6 w-6" /></div>
                <span className="tabular mt-3 text-xs font-bold text-teal-600">0{i + 1}</span>
                <h4 className="mt-1 font-semibold text-navy-700">{t(`${s.key}_title`)}</h4>
                <p className="mt-1 text-sm leading-6 text-muted">{t(`${s.key}_desc`)}</p>
              </li>
            ))}
          </ol>
          <div className="mt-14 grid gap-4 rounded-xl bg-navy-700 p-6 text-white sm:grid-cols-3 sm:p-8">
            {["principle_payments", "principle_delivery", "principle_ownership"].map((k) => (
              <div key={k} className="flex gap-3">
                <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-teal-300" />
                <div>
                  <p className="font-semibold">{t(`${k}_title`)}</p>
                  <p className="mt-1 text-sm leading-6 text-navy-100">{t(`${k}_desc`)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- features */}
      <section className="bg-white py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <SectionTitle eyebrow={t("feat_eyebrow")} title={t("feat_title")} subtitle={t("feat_subtitle")} />
          <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((f) => (
              <div key={f.key} className="rounded-xl border border-line p-6 transition hover:border-teal-200 hover:shadow-[var(--shadow-card)]">
                <f.icon className="h-6 w-6 text-teal-500" />
                <h4 className="mt-4 font-semibold text-navy-700">{t(`${f.key}_title`)}</h4>
                <p className="mt-1.5 text-sm leading-6 text-muted">{t(`${f.key}_desc`)}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- join */}
      <section className="py-20">
        <div className="mx-auto grid max-w-7xl gap-6 px-4 sm:px-6 lg:grid-cols-2">
          {[
            { k: "invite_suppliers", href: "/register?type=supplier", icon: Boxes },
            { k: "invite_reps", href: "/register?type=representative", icon: UserRound },
          ].map((c) => (
            <div key={c.k} className="relative overflow-hidden rounded-xl bg-gradient-to-br from-navy-700 to-navy-500 p-8 text-white">
              <div className="absolute -end-10 -top-10 h-40 w-40 rounded-full bg-teal-400/20 blur-2xl" />
              <c.icon className="h-8 w-8 text-teal-300" />
              <h3 className="mt-4 text-2xl font-bold">{t(`${c.k}_title`)}</h3>
              <p className="mt-2 max-w-md text-navy-100">{t(`${c.k}_desc`)}</p>
              <Link href={c.href} className="mt-6 inline-flex h-11 items-center rounded-md bg-white px-5 text-sm font-semibold text-navy-700 transition hover:bg-teal-50">
                {t(`${c.k}_cta`)}
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* ---------------------------------------------------------------- faq + contact */}
      <section id="faq" className="scroll-mt-20 bg-white py-20 sm:py-24">
        <div className="mx-auto grid max-w-7xl gap-12 px-4 sm:px-6 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <SectionTitle align="start" eyebrow={t("faq_eyebrow")} title={t("faq_title")} />
            <div className="mt-8 divide-y divide-line rounded-xl border border-line">
              {FAQ_KEYS.map((k) => (
                <details key={k} className="group p-5 [&_summary::-webkit-details-marker]:hidden">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium text-navy-700">
                    {t(`faq.${k}_q`)}
                    <span className="text-xl leading-none text-teal-500 transition group-open:rotate-45">+</span>
                  </summary>
                  <p className="mt-3 text-sm leading-7 text-muted">{t(`faq.${k}_a`)}</p>
                </details>
              ))}
            </div>
          </div>
          <div id="contact" className="lg:col-span-2">
            <SectionTitle align="start" eyebrow={t("contact_eyebrow")} title={t("contact_title")} subtitle={t("contact_subtitle")} />
            <div className="mt-8"><ContactForm /></div>
          </div>
        </div>
      </section>
      <SiteFooter />
    </>
  );
}

function SectionTitle({ eyebrow, title, subtitle, align = "center" }: { eyebrow: string; title: string; subtitle?: string; align?: "center" | "start" }) {
  return (
    <div className={align === "center" ? "mx-auto max-w-2xl text-center" : ""}>
      <p className="text-sm font-semibold uppercase tracking-wider text-teal-600">{eyebrow}</p>
      <h2 className="mt-2 text-3xl font-bold tracking-tight text-navy-700 sm:text-4xl">{title}</h2>
      {subtitle && <p className="mt-4 text-base leading-7 text-muted">{subtitle}</p>}
    </div>
  );
}

function HeroVisual({ t }: { t: (k: string) => string }) {
  const nodes = [
    { k: "node_store", icon: Store, pos: "top-[8%] start-[6%]", tone: "bg-teal-500" },
    { k: "node_rep", icon: UserRound, pos: "top-[38%] end-[2%]", tone: "bg-[#E5A13B]" },
    { k: "node_supplier", icon: Building2, pos: "bottom-[6%] start-[18%]", tone: "bg-navy-400" },
  ];
  return (
    <div className="relative mx-auto hidden aspect-square w-full max-w-[520px] sm:block" aria-hidden>
      <svg viewBox="0 0 400 400" className="absolute inset-0 h-full w-full">
        <defs>
          <linearGradient id="hl" x1="0" x2="1"><stop offset="0" stopColor="#55D6B0" /><stop offset="1" stopColor="#20B99A" /></linearGradient>
        </defs>
        <circle cx="200" cy="200" r="150" fill="none" stroke="rgba(255,255,255,.08)" strokeDasharray="4 8" />
        <circle cx="200" cy="200" r="95" fill="none" stroke="rgba(255,255,255,.08)" />
        <path d="M80 70 Q260 90 350 190 Q230 300 120 340 Q140 200 80 70" fill="none" stroke="url(#hl)" strokeWidth="2.5" strokeDasharray="6 6">
          <animate attributeName="stroke-dashoffset" from="0" to="-48" dur="3s" repeatCount="indefinite" />
        </path>
      </svg>
      <div className="absolute inset-[30%] flex items-center justify-center rounded-full bg-white/5 ring-1 ring-white/10 backdrop-blur">
        <div className="text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-teal-500 shadow-lg shadow-teal-500/40"><Handshake className="h-8 w-8" /></div>
          <p className="mt-3 text-sm font-semibold">{t("node_center")}</p>
        </div>
      </div>
      {nodes.map((n) => (
        <div key={n.k} className={`absolute ${n.pos} flex items-center gap-3 rounded-xl bg-white/95 px-4 py-3 text-navy-700 shadow-xl`}>
          <span className={`flex h-9 w-9 items-center justify-center rounded-lg text-white ${n.tone}`}><n.icon className="h-5 w-5" /></span>
          <span className="text-sm font-semibold">{t(n.k)}</span>
        </div>
      ))}
      <div className="absolute bottom-[30%] end-[8%] w-56 rounded-xl bg-white p-4 text-navy-700 shadow-2xl">
        <div className="flex items-center justify-between text-xs text-muted"><span>{t("mock_order")}</span><span className="rounded-full bg-warning/15 px-2 py-0.5 font-medium text-[#a8701f]">{t("mock_status")}</span></div>
        <div className="mt-3 space-y-2">
          <div className="h-2 w-4/5 rounded-full bg-navy-50" />
          <div className="h-2 w-3/5 rounded-full bg-navy-50" />
        </div>
        <div className="mt-4 flex gap-2">
          <span className="flex-1 rounded-md bg-teal-500 py-1.5 text-center text-xs font-semibold text-white">{t("mock_approve")}</span>
          <span className="flex-1 rounded-md bg-navy-50 py-1.5 text-center text-xs font-semibold">{t("mock_edit")}</span>
        </div>
      </div>
    </div>
  );
}
