import { createRef, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Wind, Heart, Shield, Sparkles, ArrowRight, Clock, Brain, MessagesSquare, ShieldCheck } from "lucide-react";
import { motion, useScroll, useTransform } from "framer-motion";
import { Link } from "react-router-dom";
import heroImage from "@/assets/hero-ai-therapist.png";
import BackgroundDecor from "@/components/auth/BackgroundDecor";

const preset = {
  palette: {
    background: "hsl(249 100% 98%)",
    surface: "rgba(255,255,255,0.78)",
    dark: "hsl(215 25% 27%)",
    muted: "hsl(215 16% 47%)",
    primary: "hsl(198 93% 73%)",
    accent: "hsl(142 76% 73%)",
  },
};

const shufflerSeed = [
  { label: "Anxiety", note: "Recognize emotional intensity gently" },
  { label: "Reflection", note: "Slow the moment down with guided prompts" },
  { label: "Relief", note: "Shift toward breathing, grounding, and calm" },
];

const typewriterLines = [
  "I'm here with you.",
  "Let's slow this down together.",
  "Tell me what you're feeling right now.",
  "You do not have to sort everything alone.",
];

const scheduleDays = ["S", "M", "T", "W", "T", "F", "S"];

const benefits = [
  {
    title: "Real-time emotional support",
    desc: "A responsive, judgment-free space for difficult moments, reflection, and regulation.",
    icon: MessagesSquare,
  },
  {
    title: "Personalized coping strategies",
    desc: "Breathing, reframing, journaling, and grounding guidance adapted to user needs.",
    icon: Brain,
  },
  {
    title: "Private, always-available care",
    desc: "Designed to feel safe, calm, and present whenever support is needed most.",
    icon: ShieldCheck,
  },
];

const protocolSteps = [
  {
    step: "01",
    title: "Listen",
    description:
      "The system captures emotional context through gentle prompts and reflective conversation.",
    type: "orbit" as const,
  },
  {
    step: "02",
    title: "Reflect",
    description:
      "Patterns, feelings, and triggers are surfaced with calm guidance instead of cognitive overload.",
    type: "scan" as const,
  },
  {
    step: "03",
    title: "Support",
    description:
      "Actionable next steps turn insight into soothing routines, emotional regulation, and daily care.",
    type: "wave" as const,
  },
];

function useTypewriter(lines: string[], speed = 42, pause = 1200) {
  const [lineIndex, setLineIndex] = useState(0);
  const [text, setText] = useState("");

  useEffect(() => {
    let mounted = true;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    const current = lines[lineIndex % lines.length];

    if (text.length < current.length) {
      timeout = setTimeout(() => {
        if (mounted) setText(current.slice(0, text.length + 1));
      }, speed);
    } else {
      timeout = setTimeout(() => {
        if (mounted) {
          setText("");
          setLineIndex((i) => (i + 1) % lines.length);
        }
      }, pause);
    }

    return () => {
      mounted = false;
      clearTimeout(timeout);
    };
  }, [text, lineIndex, lines, speed, pause]);

  return text;
}

function CardShell({
  title,
  desc,
  Icon,
  children,
}: {
  title: string;
  desc: string;
  Icon: typeof MessagesSquare;
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-[2rem] border p-6 shadow-[0_18px_60px_rgba(0,0,0,0.06)]"
      style={{
        background: "linear-gradient(180deg, rgba(34,49,61,0.88) 0%, rgba(24,36,47,0.78) 100%)",
        borderColor: "rgba(255,255,255,0.14)",
        backdropFilter: "blur(14px)",
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3
            className="text-2xl font-semibold tracking-[-0.03em] md:text-[1.7rem]"
            style={{
              color: "hsl(162 72% 78%)",
              textShadow: "0 1px 12px rgba(0,0,0,0.22)",
            }}
          >
            {title}
          </h3>
          <p
            className="mt-3 text-base leading-8 md:text-[1.05rem]"
            style={{
              color: "hsl(210 35% 92%)",
              textShadow: "0 1px 8px rgba(0,0,0,0.14)",
            }}
          >
            {desc}
          </p>
        </div>

        <div
          className="rounded-2xl p-3"
          style={{
            background: "rgba(255,255,255,0.12)",
            color: "hsl(210 40% 98%)",
          }}
        >
          <Icon size={20} />
        </div>
      </div>

      {children}
    </div>
  );
}

function BenefitCards() {
  const [stack, setStack] = useState(shufflerSeed);
  const typed = useTypewriter(typewriterLines);
  const [activeDay, setActiveDay] = useState(2);
  const cursorRef = useRef<HTMLDivElement | null>(null);
  const cellsRef = useRef<(HTMLDivElement | null)[]>([]);
  const saveRef = useRef<HTMLButtonElement | null>(null);
  const boardRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setStack((prev) => {
        const copy = [...prev];
        const last = copy.pop();
        if (last) copy.unshift(last);
        return copy;
      });
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!cursorRef.current || !boardRef.current || !saveRef.current) return;
    const cells = cellsRef.current.filter(Boolean) as HTMLDivElement[];
    if (!cells.length) return;

    let timeout: ReturnType<typeof setTimeout> | undefined;
    let currentStep = 0;

    const sequence = [...cells, saveRef.current];

    const animateNext = () => {
      const target = sequence[currentStep];
      if (!target || !cursorRef.current || !boardRef.current) return;

      const parentRect = boardRef.current.getBoundingClientRect();
      const targetRect = target.getBoundingClientRect();

      const x = targetRect.left - parentRect.left + targetRect.width / 2 - 10;
      const y = targetRect.top - parentRect.top + targetRect.height / 2 - 10;

      cursorRef.current.style.transition = "transform 0.35s ease, opacity 0.35s ease";
      cursorRef.current.style.transform = `translate(${x}px, ${y}px)`;

      if (currentStep < cells.length) {
        setActiveDay(currentStep);
      }

      timeout = setTimeout(() => {
        target.style.transform = "scale(0.95)";
        setTimeout(() => {
          target.style.transform = "scale(1)";
        }, 120);

        currentStep += 1;

        if (currentStep < sequence.length) {
          animateNext();
        } else {
          timeout = setTimeout(() => {
            if (cursorRef.current) {
              cursorRef.current.style.opacity = "0";
              cursorRef.current.style.transform = "translate(0px, 0px)";
            }

            timeout = setTimeout(() => {
              if (cursorRef.current) {
                cursorRef.current.style.opacity = "1";
              }
              currentStep = 0;
              animateNext();
            }, 600);
          }, 500);
        }
      }, 400);
    };

    animateNext();

    return () => clearTimeout(timeout);
  }, []);

  return (
    <section
      id="benefits"
      className="relative z-10 mx-auto max-w-6xl px-5 py-20 md:px-10 md:py-28"
    >
      <div className="mb-10 flex flex-col gap-4 md:mb-14 md:flex-row md:items-end md:justify-between">
        <div>
          <div
            className="mb-3 text-xs font-semibold uppercase tracking-[0.24em] text-primary"
          >
            Therapeutic Interfaces
          </div>
          <h2 className="text-3xl font-semibold tracking-[-0.04em] text-foreground md:text-5xl">
            Functional emotional support, shaped like calm software.
          </h2>
        </div>

        <p className="max-w-xl text-sm leading-7 text-muted-foreground md:text-base">
          Each interaction is designed to feel responsive and safe, reflecting
          emotional presence rather than performative AI.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <CardShell
          title={benefits[0].title}
          desc={benefits[0].desc}
          Icon={benefits[0].icon}
        >
          <div className="relative mt-7 h-64">
            {stack.map((item, i) => (
              <div
                key={item.label}
                className="absolute inset-x-0 mx-auto w-[92%] rounded-[1.8rem] border p-5 shadow-[0_20px_50px_rgba(0,0,0,0.08)] transition-all duration-500"
                style={{
                  top: `${i * 20}px`,
                  background:
                    i === 0 ? "rgba(255,255,255,0.95)" : "rgba(255,255,255,0.8)",
                  borderColor: "rgba(58,90,64,0.1)",
                  transform: `scale(${1 - i * 0.04})`,
                  zIndex: 10 - i,
                  transitionTimingFunction: "cubic-bezier(0.34,1.56,0.64,1)",
                }}
              >
                <div
                  className="text-xs uppercase tracking-[0.22em]"
                  style={{ color: "hsl(215 18% 28%)" }}
                >
                  Emotional State
                </div>
                <div
                  className="mt-3 text-2xl font-semibold"
                  style={{ color: preset.palette.dark }}
                >
                  {item.label}
                </div>
                <div
                  className="mt-2 text-sm leading-6"
                  style={{ color: "hsl(215 22% 24%)" }}
                >
                  {item.note}
                </div>
              </div>
            ))}
          </div>
        </CardShell>

        <CardShell
          title={benefits[1].title}
          desc={benefits[1].desc}
          Icon={benefits[1].icon}
        >
          <div
            className="mt-7 rounded-[1.8rem] border p-5 font-mono text-sm"
            style={{
              borderColor: "rgba(58,90,64,0.1)",
              background: "rgba(247,245,239,0.85)",
            }}
          >
            <div
              className="mb-4 flex items-center gap-2 text-xs uppercase tracking-[0.24em]"
              style={{ color: "hsl(215 18% 28%)" }}
            >
              <span
                className="h-2.5 w-2.5 animate-pulse rounded-full"
                style={{ background: preset.palette.accent }}
              />
              Live Support Feed
            </div>

            <div
              className="min-h-[100px] text-base leading-8"
              style={{ color: preset.palette.dark }}
            >
              {typed}
              <span
                className="ml-1 inline-block h-5 w-[2px] animate-pulse align-middle"
                style={{ background: preset.palette.accent }}
              />
            </div>

            <div className="mt-6 grid gap-3">
              {[
                "Guided breathing protocol ready",
                "Mood reframing suggestions available",
                "Journal prompt generated",
              ].map((line) => (
                <div
                  key={line}
                  className="rounded-2xl border px-4 py-3"
                  style={{
                    borderColor: "rgba(58,90,64,0.08)",
                    color: "hsl(215 22% 24%)",
                  }}
                >
                  {line}
                </div>
              ))}
            </div>
          </div>
        </CardShell>

        <CardShell
          title={benefits[2].title}
          desc={benefits[2].desc}
          Icon={benefits[2].icon}
        >
          <div
            ref={boardRef}
            className="relative mt-7 rounded-[1.8rem] border p-5"
            style={{
              borderColor: "rgba(58,90,64,0.1)",
              background: "rgba(255,255,255,0.9)",
            }}
          >
            <div
              className="grid grid-cols-7 gap-2 text-center text-xs uppercase tracking-[0.22em]"
              style={{ color: "hsl(215 18% 28%)" }}
            >
              {scheduleDays.map((day, idx) => (
                <div
                  key={`${day}-${idx}`}
                  ref={(el) => {
                    cellsRef.current[idx] = el;
                  }}
                  className="day-cell rounded-2xl border px-0 py-4 transition-all duration-300"
                  style={{
                    borderColor:
                      activeDay === idx
                        ? "transparent"
                        : "rgba(58,90,64,0.08)",
                    background:
                      activeDay === idx
                        ? preset.palette.accent
                        : "rgba(247,245,239,0.9)",
                    color:
                      activeDay === idx
                        ? preset.palette.dark
                        : "hsl(215 20% 24%)",
                    boxShadow:
                      activeDay === idx
                        ? "0 10px 30px rgba(0,0,0,0.08)"
                        : "none",
                  }}
                >
                  {day}
                </div>
              ))}
            </div>

            <div
              className="mt-5 rounded-2xl border p-4 text-sm"
              style={{
                borderColor: "rgba(58,90,64,0.08)",
                color: "hsl(215 22% 24%)",
              }}
            >
              Breathing sessions · Journaling · Evening check-ins
            </div>

            <button
              ref={saveRef}
              className="save-btn mt-4 rounded-full px-4 py-2 text-sm font-medium transition-transform duration-150"
              style={{
                background: preset.palette.primary,
                color: preset.palette.background,
              }}
            >
              Save Routine
            </button>

            <div
              ref={cursorRef}
              className="pointer-events-none absolute left-0 top-0 text-xl transition-all duration-300"
            >
              ⌁
            </div>
          </div>
        </CardShell>
      </div>
    </section>
  );
}

function ProtocolCard({
  item,
  nextCardRef,
  cardRef,
}: {
  item: (typeof protocolSteps)[number];
  nextCardRef: React.RefObject<HTMLDivElement> | null;
  cardRef: React.RefObject<HTMLDivElement>;
}) {
  const { scrollYProgress } = useScroll(
    nextCardRef
      ? {
          target: nextCardRef,
          offset: ["start 80%", "start 30%"],
        }
      : undefined,
  );

  const scale = useTransform(scrollYProgress, [0, 1], [1, 0.9]);
  const opacity = useTransform(scrollYProgress, [0, 1], [1, 0.5]);
  const blur = useTransform(scrollYProgress, [0, 1], ["blur(0px)", "blur(20px)"]);

  return (
    <motion.div
      ref={cardRef}
      className="protocol-card sticky top-24 grid min-h-[82vh] items-center gap-10 rounded-[2.5rem] border px-6 py-8 shadow-[0_24px_80px_rgba(0,0,0,0.08)] md:grid-cols-2 md:px-10 md:py-10"
      style={{
        background: "linear-gradient(180deg, rgba(34,49,61,0.88) 0%, rgba(24,36,47,0.78) 100%)",
        borderColor: "rgba(255,255,255,0.14)",
        backdropFilter: "blur(16px)",
        scale: nextCardRef ? scale : 1,
        opacity: nextCardRef ? opacity : 1,
        filter: nextCardRef ? blur : "blur(0px)",
        willChange: "transform, opacity, filter",
      }}
    >
      <div>
        <div
          className="font-mono text-sm uppercase tracking-[0.24em]"
          style={{ color: "hsl(162 72% 78%)" }}
        >
          Step {item.step}
        </div>

        <h3
          className="mt-4 text-3xl font-semibold tracking-[-0.04em] md:text-5xl"
          style={{
            color: "hsl(210 40% 98%)",
            textShadow: "0 1px 12px rgba(0,0,0,0.22)",
          }}
        >
          {item.title}
        </h3>

        <p
          className="mt-5 max-w-xl text-base leading-8 md:text-lg"
          style={{
            color: "hsl(210 35% 92%)",
            textShadow: "0 1px 8px rgba(0,0,0,0.14)",
          }}
        >
          {item.description}
        </p>
      </div>

      <ProtocolVisual type={item.type} />
    </motion.div>
  );
}

function Protocol() {
  const cardRefs = useRef(protocolSteps.map(() => createRef<HTMLDivElement>()));

  return (
    <section id="protocol" className="px-5 py-20 md:px-10 md:py-28">
      <div className="mx-auto max-w-6xl">
        <div className="mb-10 md:mb-14">
          <div
            className="mb-3 text-xs uppercase tracking-[0.24em]"
            style={{ color: "hsl(var(--primary))" }}
          >
            Path To Healing
          </div>

          <h2
            className="max-w-3xl text-3xl font-semibold tracking-[-0.04em] md:text-5xl"
            style={{
              color: "hsl(0 0% 100%)",
              textShadow: "0 1px 12px rgba(0,0,0,0.22)",
            }}
          >
            A responsive therapeutic flow that listens first, then helps users stabilize.
          </h2>
        </div>

        <div className="space-y-8">
          {protocolSteps.map((item, index) => (
            <ProtocolCard
              key={item.step}
              item={item}
              cardRef={cardRefs.current[index]}
              nextCardRef={cardRefs.current[index + 1] ?? null}
            />
          ))}
        </div>
      </div>
    </section>
  );
}

function ProtocolVisual({ type }: { type: (typeof protocolSteps)[number]["type"] }) {
  if (type === "orbit") {
    return (
      <div
        className="flex h-[360px] items-center justify-center rounded-[2rem]"
        style={{
          background:
            "linear-gradient(180deg, rgba(58,90,64,0.08), rgba(212,163,115,0.12))",
        }}
      >
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 18, ease: "linear" }}
          className="relative h-56 w-56 rounded-full border"
          style={{ borderColor: "rgba(58,90,64,0.2)" }}
        >
          <div
            className="absolute inset-8 rounded-full border"
            style={{ borderColor: "rgba(212,163,115,0.35)" }}
          />
          <div
            className="absolute left-1/2 top-0 h-5 w-5 -translate-x-1/2 rounded-full"
            style={{ background: preset.palette.accent }}
          />
          <div
            className="absolute bottom-8 left-8 h-4 w-4 rounded-full"
            style={{ background: preset.palette.primary }}
          />
        </motion.div>
      </div>
    );
  }

  if (type === "scan") {
    return (
      <div
        className="relative h-[360px] overflow-hidden rounded-[2rem] border"
        style={{
          borderColor: "rgba(58,90,64,0.1)",
          background: "rgba(247,245,239,0.72)",
        }}
      >
        <div className="grid h-full grid-cols-9 gap-4 p-8 opacity-60">
          {Array.from({ length: 81 }).map((_, i) => (
            <div
              key={i}
              className="aspect-square rounded-full"
              style={{ background: "rgba(58,90,64,0.18)" }}
            />
          ))}
        </div>

        <motion.div
          className="absolute left-0 right-0 h-10"
          style={{
            background:
              "linear-gradient(180deg, rgba(212,163,115,0), rgba(212,163,115,0.7), rgba(212,163,115,0))",
          }}
          animate={{ y: [0, 300, 0] }}
          transition={{ repeat: Infinity, duration: 3.4, ease: "easeInOut" }}
        />
      </div>
    );
  }

  return (
    <div
      className="flex h-[360px] items-center justify-center rounded-[2rem] border px-6"
      style={{
        borderColor: "rgba(58,90,64,0.1)",
        background: "rgba(247,245,239,0.72)",
      }}
    >
      <svg viewBox="0 0 500 180" className="w-full">
        <motion.path
          d="M0 100 C 30 100, 30 40, 60 40 S 90 160, 120 160 S 150 60, 180 60 S 210 110, 240 110 S 270 30, 300 30 S 330 140, 360 140 S 390 90, 420 90 S 450 70, 500 70"
          fill="none"
          stroke={preset.palette.primary}
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray="16 10"
          animate={{ strokeDashoffset: [0, -120] }}
          transition={{ repeat: Infinity, duration: 4, ease: "linear" }}
        />
      </svg>
    </div>
  );
}

export default function Landing() {
  useEffect(() => {
    const search = new URLSearchParams(window.location.search);
    const error = search.get("error");
    const errorCode = search.get("error_code");
    if (error || errorCode) {
      // #region agent log
      fetch("http://127.0.0.1:7498/ingest/de8af993-af91-47ad-aef8-03b59e70199a", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "a2dded" },
        body: JSON.stringify({
          sessionId: "a2dded",
          location: "Landing.tsx:oauth_error",
          message: "Supabase OAuth error on Site URL root",
          data: {
            error,
            errorCode,
            path: window.location.pathname,
            origin: window.location.origin,
            hashLen: window.location.hash.length,
          },
          hypothesisId: "H2-H5",
          runId: "pre-fix",
          timestamp: Date.now(),
        }),
      }).catch(() => {});
      // #endregion
    }
  }, []);

  return (
    <div className="min-h-screen relative flex flex-col bg-gradient-to-br from-primary/10 via-background to-secondary/10 selection:bg-primary/30 overflow-x-hidden">
      <BackgroundDecor />
      {/* Header */}
      <header className="border-b bg-background/40 backdrop-blur-xl sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-4 group cursor-pointer" onClick={() => window.location.href = '/'}>
            <div className="relative w-10 h-10 flex items-center justify-center">
              <Wind className="absolute text-primary/40 animate-pulse" size={32} strokeWidth={1.5} />
              <Sparkles className="absolute text-accent/60 -top-1 -right-1 animate-bounce" size={16} />
            </div>
            <span className="flex flex-col leading-tight">
              <span className="text-2xl font-light tracking-[0.25em] uppercase">
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-secondary to-accent">Ella AI</span>
              </span>
              <span className="text-[9px] uppercase tracking-[0.35em] text-muted-foreground/70">by 3AM Talks</span>
            </span>
          </div>
          <div className="flex gap-2">
            <Button asChild variant="outline">
              <Link to="/auth">Sign In</Link>
            </Button>
            <Button asChild>
              <Link to="/auth">Get Started</Link>
            </Button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-20 px-4">
        <div className="container mx-auto max-w-6xl">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-8">
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-primary">
                  <Sparkles className="h-5 w-5" />
                  <span className="text-sm font-medium">3AM Talks · AI Mental Health Assistant</span>
                </div>
                <h1 className="text-5xl md:text-7xl font-extralight leading-tight tracking-tight uppercase">
                  Your Personal{" "}
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-secondary to-accent font-black tracking-tighter italic">
                    Ella AI
                  </span>
                </h1>
                <p className="text-xl text-muted-foreground max-w-lg">
                  Get compassionate support, track your mental health journey, and build better habits with our AI-powered therapy assistant available 24/7.
                </p>
              </div>

              <div className="flex flex-col sm:flex-row gap-4">
                <Button asChild size="lg" className="shadow-lg">
                  <Link to="/auth" className="flex items-center gap-2">
                    Start Your Journey <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
                <Button asChild variant="outline" size="lg">
                  <Link to="/learn-more">Learn More</Link>
                </Button>
              </div>

              <div className="flex items-center gap-8 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-green-500" />
                  <span>100% Private & Secure</span>
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-blue-500" />
                  <span>Available 24/7</span>
                </div>
              </div>
            </div>

            <div className="relative">
              <div className="relative z-10">
                <img
                  src={heroImage}
                  alt="AI Therapist Assistant"
                  className="w-full h-auto rounded-2xl shadow-2xl"
                />
              </div>
              <div className="absolute inset-0 bg-gradient-to-tr from-primary/20 to-secondary/20 rounded-2xl blur-3xl -z-10 transform scale-105"></div>
            </div>
          </div>
        </div>
      </section>

      <BenefitCards />
      <Protocol />

      {/* CTA Section */}
      <section className="py-20 px-4">
        <div className="container mx-auto max-w-4xl text-center">
          <Card className="border-0 shadow-xl bg-gradient-to-br from-primary/5 to-secondary/5">
            <CardHeader className="space-y-6 py-12">
              <div className="flex justify-center">
                <div className="flex items-center gap-2">
                  <Heart className="h-8 w-8 text-primary" />
                  <Wind className="h-8 w-8 text-secondary" />
                  <Sparkles className="h-8 w-8 text-accent" />
                </div>
              </div>
              <CardTitle className="text-3xl md:text-4xl">
                Ready to start your mental wellness journey?
              </CardTitle>
              <CardDescription className="text-lg max-w-2xl mx-auto">
                Join thousands of users who have found comfort, support, and growth with our AI therapy assistant.
                Your mental health matters, and we're here to help you thrive.
              </CardDescription>
              <div className="pt-4">
                <Button asChild size="lg" className="shadow-lg">
                  <Link to="/auth" className="flex items-center gap-2">
                    Get Started Free <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              </div>
            </CardHeader>
          </Card>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-8 px-4">
        <div className="container mx-auto text-center text-muted-foreground">
          <p>&copy; 2026 3AM Talks · Ella AI — AI Mental Health Assistant.</p>
        </div>
      </footer>
    </div>
  );
}
