"use client";

import React, { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { InteractiveHoverButton } from "@/components/ui/interactive-hover-button";
import { Pricing } from "@/components/pricing";
import SkyToggle from "@/components/ui/sky-toggle";
import { GlowingEffect } from "@/components/ui/glowing-effect";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import {
  ScanText,
  BarChart3,
  FileText,
  Zap,
  Users,
  ShieldCheck,
  ArrowRight,
  GraduationCap,
  Star,
  Clock,
  TrendingDown,
  Frown,
  ChevronRight,
  Sparkles,
  BookOpen,
  Award,
} from "lucide-react";

/* ─── Colors ─────────────────────────────────────────────── */
const PRIMARY = "#C08552";
const SECONDARY = "#8C5A3C";
const DARK = "#4B2E2B";
const CREAM = "#FFF8F0";

/* ─── Data ─────────────────────────────────────────────────── */
const painPoints = [
  {
    icon: Clock,
    title: "Des heures perdues à corriger",
    desc: "Un enseignant passe en moyenne 6h par semaine à corriger des copies — du temps volé à la pédagogie.",
  },
  {
    icon: TrendingDown,
    title: "L'incohérence de notation",
    desc: "La fatigue engendre des erreurs et des incohérences dans les notes d'un même examen.",
  },
  {
    icon: Frown,
    title: "Retour tardif aux étudiants",
    desc: "Les étudiants attendent parfois des semaines pour connaître leurs résultats et comprendre leurs erreurs.",
  },
];

const steps = [
  {
    num: "01",
    icon: BookOpen,
    title: "Scannez les copies",
    desc: "Photographiez ou numérisez les examens manuscrits. Notre OCR reconnaît toutes les écritures.",
    color: PRIMARY,
  },
  {
    num: "02",
    icon: BarChart3,
    title: "Définissez votre barème",
    desc: "Créez votre grille d'évaluation une fois. Sallahli l'applique à chaque copie avec précision.",
    color: SECONDARY,
  },
  {
    num: "03",
    icon: Award,
    title: "Obtenez les résultats",
    desc: "Notes, commentaires personnalisés et rapports détaillés générés instantanément.",
    color: DARK,
  },
];

const testimonials = [
  {
    name: "Prof. Amel Bouaziz",
    role: "Lycée Ibn Khaldoun, Tunis",
    text: "Sallahli m'a rendu mes soirées. Je corrige 120 copies en moins de 5 minutes là où j'en passais 4 heures.",
    stars: 5,
    initials: "AB",
  },
  {
    name: "Dr. Karim Mansouri",
    role: "Université de Sfax",
    text: "La précision de la reconnaissance OCR est bluffante. Même les écritures les plus difficiles sont correctement lues.",
    stars: 5,
    initials: "KM",
  },
  {
    name: "Mme. Nadia Harrabi",
    role: "Collège El Manar, Alger",
    text: "Les rapports m'aident à cibler mes interventions. J'enseigne maintenant de façon beaucoup plus stratégique.",
    stars: 5,
    initials: "NH",
  },
];

const stats = [
  { value: "50 000+", label: "Copies corrigées" },
  { value: "98.7%", label: "Précision OCR" },
  { value: "200+", label: "Établissements" },
  { value: "10×", label: "Plus rapide" },
];

const pricingPlans = [
  {
    name: "Gratuit",
    price: "0",
    yearlyPrice: "0",
    period: "par mois",
    description: "Parfait pour tester la puissance de l'IA Sallahli.",
    buttonText: "Commencer gratuitement",
    href: "#",
    isPopular: false,
    features: ["5 copies par mois", "OCR Standard", "Export PDF", "Accès communauté"],
  },
  {
    name: "Enseignant",
    price: "29",
    yearlyPrice: "290",
    period: "par mois",
    description: "Le choix des professionnels de l'éducation.",
    buttonText: "Devenir Pro",
    href: "#",
    isPopular: true,
    features: [
      "Copies illimitées",
      "OCR Premium (manuscrit)",
      "Analyses d'IA détaillées",
      "Export Excel & PDF",
      "Support prioritaire",
    ],
  },
  {
    name: "Établissement",
    price: "199",
    yearlyPrice: "1990",
    period: "par mois",
    description: "Pour les lycées et universités modernes.",
    buttonText: "Contacter l'équipe",
    href: "#",
    isPopular: false,
    features: [
      "Multicptes enseignants",
      "Tableau de bord admin",
      "Intégration ENT / API",
      "SSO & Sécurité renforcée",
      "Formation en distanciel",
    ],
  },
];

/* ─── Glowing Grid Component ────────────────────────────────── */
interface GridItemProps {
  area: string;
  icon: React.ReactNode;
  title: string;
  description: React.ReactNode;
}

const GridItem = ({ area, icon, title, description }: GridItemProps) => {
  return (
    <li className={cn("min-h-[14rem] list-none", area)}>
      <div className="relative h-full rounded-[1.25rem] border-[0.75px] border-border p-2 md:rounded-[1.5rem] md:p-3">
        <GlowingEffect
          spread={40}
          glow={true}
          disabled={false}
          proximity={64}
          inactiveZone={0.01}
          borderWidth={3}
        />
        <div className="relative flex h-full flex-col justify-between gap-6 overflow-hidden rounded-xl border-[0.75px] bg-background p-6 shadow-sm dark:shadow-[0px_0px_27px_0px_rgba(45,45,45,0.3)] md:p-6 transition-all duration-300 hover:shadow-lg cursor-pointer">
          <div className="relative flex flex-1 flex-col justify-between gap-3">
            <div className="w-fit rounded-lg border-[0.75px] border-border bg-muted p-2" style={{ color: PRIMARY }}>
              {icon}
            </div>
            <div className="space-y-3">
              <h3 className="pt-0.5 text-xl leading-[1.375rem] font-bold tracking-[-0.04em] md:text-2xl md:leading-[1.875rem] text-balance text-foreground font-serif">
                {title}
              </h3>
              <h2 className="font-sans text-sm leading-[1.125rem] md:text-base md:leading-[1.375rem] text-muted-foreground">
                {description}
              </h2>
            </div>
          </div>
        </div>
      </div>
    </li>
  );
};


/* ─── Component ────────────────────────────────────────────── */
export default function LandingPage() {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const isDark = mounted && resolvedTheme === "dark";

  const [titleNumber, setTitleNumber] = useState(0);
  const titles = React.useMemo(
    () => ["réinventée ", "accélérée ", "simplifiée ", "automatisée ", "sublimée "],
    []
  );

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (titleNumber === titles.length - 1) {
        setTitleNumber(0);
      } else {
        setTitleNumber(titleNumber + 1);
      }
    }, 2500);
    return () => clearTimeout(timeoutId);
  }, [titleNumber, titles]);

  const text = isDark ? `text-[${CREAM}]` : `text-[${DARK}]`;
  const muted = isDark ? "text-white/70" : `text-[${SECONDARY}]`;

  return (
    <div className={`min-h-screen ${isDark ? "hero-bg-dark" : "hero-bg-light"} transition-colors duration-500`}>

      {/* ── FLOATING NAVBAR ───────────────────────────────── */}
      <header className="fixed top-4 left-4 right-4 z-50">
        <nav className={`navbar-glass rounded-2xl px-5 py-3 flex items-center justify-between`}>
          {/* Logo */}
          <a href="#" className="flex items-center gap-2 cursor-pointer">
            <div className="w-8 h-8 rounded-xl overflow-hidden flex items-center justify-center shadow-lg bg-white/10">
              <img src="/logo.png" alt="Sallahli Logo" className="w-full h-full object-contain" />
            </div>
            <span className="text-xl font-800 tracking-tight gradient-text font-bold italic font-serif">Sallahli</span>
          </a>

          {/* Links */}
          <div className="hidden md:flex items-center gap-7">
            {[
              ["Fonctionnalités", "#fonctionnalités"],
              ["Comment ça marche", "#solution"],
              ["Tarifs", "#tarifs"],
              ["Témoignages", "#témoignages"],
            ].map(([label, href]) => (
              <a
                key={label}
                href={href}
                className={`text-sm font-medium transition-colors duration-200 cursor-pointer ${muted} hover:text-[#C08552]`}
              >
                {label}
              </a>
            ))}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            <SkyToggle />
            <InteractiveHoverButton
              text="Commencer"
              className="hidden md:flex h-9 text-sm rounded-xl border-0 shadow-md"
            />
          </div>
        </nav>
      </header>

      {/* ── HERO ─────────────────────────────────────────── */}
      <section className="pt-36 pb-24 container-grid text-center relative">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full mb-6 fade-up text-sm font-medium"
          style={{ border: `1px solid ${PRIMARY}33`, backgroundColor: `${PRIMARY}11`, color: PRIMARY }}>
          <Sparkles className="w-3.5 h-3.5" />
          Propulsé par l&apos;Intelligence Artificielle
        </div>

        {/* H1 */}
        <h1 className={`text-5xl md:text-[5.5rem] font-bold leading-[1.05] tracking-tight mb-6 fade-up delay-1 ${text}`}>
          La correction d&apos;examens
          <br />
          <span className="relative flex w-full justify-center overflow-hidden text-center md:pb-4 md:pt-1 h-[1.2em]">
            {titles.map((title, index) => (
              <motion.span
                key={index}
                className="absolute gradient-text italic font-serif"
                initial={{ opacity: 0, y: "-100%" }}
                transition={{ type: "spring", stiffness: 50 }}
                animate={
                  titleNumber === index
                    ? { y: 0, opacity: 1 }
                    : { y: titleNumber > index ? "-150%" : "150%", opacity: 0 }
                }
              >
                {title} par l&apos;IA.
              </motion.span>
            ))}
          </span>
        </h1>

        <p className={`text-xl md:text-2xl font-light max-w-2xl mx-auto mb-10 fade-up delay-2 ${muted} font-sans`}>
          Corrigez des centaines de copies manuscrites en quelques secondes.
          Grâce à Sallahli, les enseignants retrouvent le temps d&apos;enseigner.
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center fade-up delay-3">
          <InteractiveHoverButton
            text="Essayer gratuitement"
            className="h-12 w-full sm:w-auto text-base rounded-xl shadow-lg"
          />
          <Button
            size="lg"
            variant="outline"
            className={`h-12 px-8 text-base font-semibold rounded-xl transition-colors duration-200 cursor-pointer font-sans ${text}`}
            style={{ borderColor: `${DARK}40`, backgroundColor: 'transparent' }}
          >
            Voir la démo
          </Button>
        </div>

        {/* Trust bar */}
        <div className={`flex items-center justify-center gap-2 mt-8 fade-up delay-4 ${muted} text-sm font-sans`}>
          <div className="flex -space-x-2">
            {[["AB", PRIMARY], ["KM", SECONDARY], ["NH", DARK], ["BT", PRIMARY]].map(([l, c], i) => (
              <div key={i} className={`w-7 h-7 rounded-full flex items-center justify-center text-[${CREAM}] text-xs font-bold ring-2`}
                style={{ background: c, borderColor: isDark ? DARK : CREAM }}>
                {l[0]}
              </div>
            ))}
          </div>
          <span><strong className={text}>200+</strong> établissements nous font confiance</span>
        </div>

        {/* Dashboard mock */}
        <div className="fade-up delay-5 mt-16 max-w-3xl mx-auto font-sans">
          <div className="glass-card p-1.5">
            <div className={`rounded-[10px] p-5`} style={{ backgroundColor: isDark ? `${DARK}22` : `${CREAM}80` }}>
              <div className="flex items-center gap-1.5 mb-4">
                {["#f87171", "#fbbf24", "#34d399"].map(c => (
                  <div key={c} className="w-2.5 h-2.5 rounded-full" style={{ background: c }} />
                ))}
                <div className={`ml-auto text-xs font-medium ${muted}`}>Sallahli · Classe Terminale S</div>
              </div>
              <div className="grid grid-cols-3 gap-3 mb-3">
                {[
                  { label: "Copies traitées", val: "87/90", color: PRIMARY },
                  { label: "Note moyenne", val: "13.4/20", color: SECONDARY },
                  { label: "Temps économisé", val: "4h 12min", color: DARK },
                ].map((s, i) => (
                  <div key={i} className={`rounded-xl p-3 text-center border`} style={{ backgroundColor: isDark ? 'rgba(255,255,255,0.05)' : '#fff', borderColor: isDark ? 'rgba(255,255,255,0.05)' : `${PRIMARY}22` }}>
                    <p className="text-xl font-bold font-serif" style={{ color: isDark ? CREAM : s.color }}>{s.val}</p>
                    <p className={`text-xs mt-0.5 ${muted}`}>{s.label}</p>
                  </div>
                ))}
              </div>
              <div className={`rounded-xl p-3 border`} style={{ backgroundColor: isDark ? 'rgba(255,255,255,0.05)' : '#fff', borderColor: isDark ? 'rgba(255,255,255,0.05)' : `${PRIMARY}22` }}>
                <div className={`text-xs font-medium mb-2 ${muted} flex justify-between`}>
                  <span>Distribution des notes</span>
                </div>
                <div className="flex items-end gap-1 h-10">
                  {[30, 55, 80, 95, 72, 88, 60, 78, 91, 65, 84, 50].map((h, i) => (
                    <div key={i} className="flex-1 rounded-sm transition-all"
                      style={{
                        height: `${h}%`,
                        background: `linear-gradient(to top, ${PRIMARY}, ${SECONDARY})`,
                        opacity: 0.55 + (i % 3) * 0.15,
                      }} />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── STATS BAR ────────────────────────────────────── */}
      <section className="py-10 container-grid">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {stats.map((s, i) => (
            <div key={i} className="glass-card p-5 text-center cursor-default">
              <p className="text-3xl font-extrabold gradient-text font-serif">{s.value}</p>
              <p className={`text-sm mt-1 ${muted} font-sans`}>{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CHAPTER 1: PROBLEM ───────────────────────────── */}
      <section className={`py-24 transition-colors duration-500 chapter-problem`}>
        <div className="container-grid">
          <div className="text-center mb-14">
            <span className="text-xs font-semibold tracking-widest uppercase mb-3 block font-sans" style={{ color: PRIMARY }}>Le problème</span>
            <h2 className={`text-4xl md:text-5xl font-bold leading-tight mb-4 ${text}`}>
              La correction, un <span style={{ color: SECONDARY }}>fardeau</span> quotidien
            </h2>
            <p className={`text-lg max-w-xl mx-auto ${muted} font-sans`}>
              Chaque semaine, des milliers d&apos;enseignants sacrifient leur temps personnel pour corriger des piles de copies.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {painPoints.map((p, i) => {
              const Icon = p.icon;
              return (
                <div key={i} className={`glass-card p-6 cursor-default`}>
                  <div className="w-11 h-11 rounded-xl flex items-center justify-center mb-4" style={{ backgroundColor: `${SECONDARY}15` }}>
                    <Icon className="w-5 h-5" style={{ color: SECONDARY }} />
                  </div>
                  <h3 className={`text-base font-bold mb-2 ${text} font-serif`}>{p.title}</h3>
                  <p className={`text-sm leading-relaxed ${muted} font-sans`}>{p.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── CHAPTER 2: SOLUTION ──────────────────────────── */}
      <section id="solution" className="py-24 container-grid">
        <div className="text-center mb-14">
          <span className="text-xs font-semibold tracking-widest uppercase mb-3 block font-sans" style={{ color: PRIMARY }}>La solution</span>
          <h2 className={`text-4xl md:text-5xl font-bold leading-tight mb-4 ${text}`}>
            Comment <span className="gradient-text italic font-serif">Sallahli</span> fonctionne
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative">
          {steps.map((s, i) => {
            const Icon = s.icon;
            return (
              <div key={i} className={`glass-card p-7 text-center cursor-default step-connector`}>
                <div className="text-5xl font-black mb-4 opacity-10 font-serif" style={{ color: s.color }}>
                  {s.num}
                </div>
                <div className="w-14 h-14 rounded-2xl mx-auto mb-5 flex items-center justify-center shadow-lg"
                  style={{ background: `linear-gradient(135deg, ${s.color}22, ${s.color}44)`, border: `1px solid ${s.color}33` }}>
                  <Icon className="w-7 h-7" style={{ color: s.color }} />
                </div>
                <h3 className={`text-lg font-bold mb-2 ${text} font-serif`}>{s.title}</h3>
                <p className={`text-sm leading-relaxed ${muted} font-sans`}>{s.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── CHAPTER 3: FEATURES (GLOWING GRID) ────────────── */}
      <section id="fonctionnalités" className={`py-24 transition-colors duration-500 chapter-problem`}>
        <div className="container-grid">
          <div className="text-center mb-14">
            <span className="text-xs font-semibold tracking-widest uppercase mb-3 block font-sans" style={{ color: PRIMARY }}>Fonctionnalités</span>
            <h2 className={`text-4xl md:text-5xl font-bold leading-tight mb-4 ${text}`}>
              Tout ce dont vous avez <span className="gradient-text italic font-serif">besoin</span>
            </h2>
          </div>

          <ul className="grid grid-cols-1 grid-rows-none gap-4 md:grid-cols-12 md:grid-rows-3 lg:gap-4 xl:max-h-[34rem] xl:grid-rows-2">
            <GridItem
              area="md:[grid-area:1/1/2/7] xl:[grid-area:1/1/2/5]"
              icon={<ScanText className="h-5 w-5" />}
              title="OCR Haute-Précision"
              description="Déchiffre même les écritures manuscrites les plus difficiles avec une précision de 98,7%."
            />
            <GridItem
              area="md:[grid-area:1/7/2/13] xl:[grid-area:2/1/3/5]"
              icon={<Zap className="h-5 w-5" />}
              title="Vitesse Instantanée"
              description="Traitez jusqu'à 120 copies en moins de 5 minutes. Retrouvez votre temps perdu."
            />
            <GridItem
              area="md:[grid-area:2/1/3/7] xl:[grid-area:1/5/3/8]"
              icon={<BarChart3 className="h-5 w-5" />}
              title="Barèmes Intelligents"
              description="Créez des grilles complexes d'évaluation appliquées sans erreur à chaque copie."
            />
            <GridItem
              area="md:[grid-area:2/7/3/13] xl:[grid-area:1/8/2/13]"
              icon={<FileText className="h-5 w-5" />}
              title="Rapports Détaillés"
              description="Analyses statistiques par étudiant pour toujours mieux cibler et orienter vos futurs cours."
            />
            <GridItem
              area="md:[grid-area:3/1/4/13] xl:[grid-area:2/8/3/13]"
              icon={<ShieldCheck className="h-5 w-5" />}
              title="Données Sécurisées"
              description="Hébergement européen avec chiffrement de bout en bout. Totalement conforme au standard RGPD."
            />
          </ul>
        </div>
      </section>

      {/* ── CHAPTER 4: PRICING ────────────────────────────── */}
      <section id="tarifs" className="py-24 border-y transition-colors duration-500 chapter-problem" style={{ borderColor: `${PRIMARY}11` }}>
        <Pricing 
          plans={pricingPlans}
          title="Une tarification simple et transparente"
          description="Choisissez le forfait qui correspond à votre volume de copies."
        />
      </section>

      {/* ── TESTIMONIALS ────────────────────────────────── */}
      <section id="témoignages" className="py-24 container-grid">
        <div className="text-center mb-14">
          <span className="text-xs font-semibold tracking-widest uppercase mb-3 block font-sans" style={{ color: PRIMARY }}>Témoignages</span>
          <h2 className={`text-4xl md:text-5xl font-bold mb-4 ${text}`}>
            Ils ont <span className="gradient-text italic font-serif">adopté</span> Sallahli
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {testimonials.map((t, i) => (
            <div key={i} className="glass-card p-6 cursor-default flex flex-col gap-4">
              <div className="flex gap-0.5">
                {Array.from({ length: t.stars }).map((_, j) => (
                  <Star key={j} className="w-4 h-4 text-amber-500 fill-amber-500" />
                ))}
              </div>
              <p className={`text-sm leading-relaxed italic flex-1 ${muted} font-sans`}>
                &ldquo;{t.text}&rdquo;
              </p>
              <div className="flex items-center gap-3 pt-2 border-t" style={{ borderColor: `${PRIMARY}22` }}>
                <div className={`w-9 h-9 rounded-full flex items-center justify-center text-[${CREAM}] text-xs font-bold font-sans`} style={{ background: `linear-gradient(to bottom right, ${PRIMARY}, ${SECONDARY})` }}>
                  {t.initials}
                </div>
                <div>
                  <p className={`text-sm font-bold ${text} font-serif`}>{t.name}</p>
                  <p className={`text-xs ${muted} font-sans`}>{t.role}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── CLIMAX CTA ───────────────────────────────────── */}
      <section className="py-8 px-4 md:px-8">
        <div className="max-w-4xl mx-auto">
          <div className="rounded-3xl overflow-hidden relative"
            style={{ background: `linear-gradient(135deg, ${PRIMARY} 0%, ${SECONDARY} 50%, ${DARK} 100%)` }}>
            <div className="absolute inset-0 opacity-10"
              style={{ backgroundImage: `radial-gradient(circle at 80% 20%, ${CREAM} 1px, transparent 1px), radial-gradient(circle at 20% 70%, ${CREAM} 1px, transparent 1px)`, backgroundSize: "40px 40px" }} />
            <div className="relative px-10 py-14 text-center">
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full mb-5 text-sm font-medium font-sans" style={{ backgroundColor: 'rgba(255,255,255,0.15)', color: CREAM }}>
                <Zap className="w-3.5 h-3.5" />
                30 jours gratuits — aucune carte requise
              </div>
              <h2 className="text-4xl md:text-5xl font-bold mb-4 leading-tight font-serif" style={{ color: CREAM }}>
                Prêt à récupérer<br />votre temps libre ?
              </h2>
              <p className="text-white/80 text-lg mb-8 max-w-xl mx-auto font-sans">
                Rejoignez 200+ établissements qui corrigent plus vite, plus justement,
                avec Sallahli.
              </p>
              <div className="flex flex-col sm:flex-row gap-3 justify-center">
                <InteractiveHoverButton
                  text="Commencer maintenant"
                  className="h-12 w-full sm:w-auto text-base rounded-xl shadow-lg border-0 bg-transparent text-white"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── FOOTER ──────────────────────────────────────── */}
      <footer className={`mt-16 py-10 border-t`} style={{ borderColor: `${PRIMARY}22` }}>
        <div className="container-grid flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg overflow-hidden flex items-center justify-center bg-white/10">
              <img src="/logo.png" alt="Sallahli Logo" className="w-full h-full object-contain" />
            </div>
            <span className="font-bold gradient-text italic font-serif text-lg">Sallahli</span>
          </div>
          <p className={`text-sm ${muted} font-sans`}>© 2026 Sallahli. Tous droits réservés.</p>
          <div className="flex gap-5">
            {["Confidentialité", "Conditions", "Contact"].map(l => (
              <a key={l} href="#"
                className={`text-sm transition-colors duration-200 cursor-pointer ${muted} font-sans hover:text-[#C08552]`}>
                {l}
              </a>
            ))}
          </div>
        </div>
      </footer>

    </div>
  );
}
