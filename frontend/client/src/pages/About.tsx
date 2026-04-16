import { useState, useRef } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import {
  Heart,
  Brain,
  Shield,
  Users,
  Award,
  Sparkles,
  ArrowRight,
  CheckCircle,
  Star,
  Zap,
  Globe,
  Lock,
  Github,
  Linkedin,
  ExternalLink,
  MessageCircle,
  Coffee,
  Code2,
  Clock
} from "lucide-react";
import { Navigation, MobileNavigation } from "@/components/Navigation";
import { motion, useScroll, useTransform, useInView } from "framer-motion";
import { useNavigate } from "react-router-dom";

const FadeInWhenVisible = ({ children, delay = 0 }: { children: React.ReactNode, delay?: number }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-100px" }}
      transition={{ duration: 0.8, delay, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
};

export default function About() {
  const [isLearnMoreOpen, setIsLearnMoreOpen] = useState(false);
  const navigate = useNavigate();
  const targetRef = useRef(null);
  const { scrollYProgress } = useScroll({
    target: targetRef,
    offset: ["start start", "end start"],
  });

  const opacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);
  const scale = useTransform(scrollYProgress, [0, 0.5], [1, 0.8]);
  const y = useTransform(scrollYProgress, [0, 0.5], [0, -50]);

  const features = [
    {
      icon: Brain,
      title: "Neural Empathy",
      description: "Our proprietary AI recognizes subtle emotional cues to provide truly personalized support.",
      color: "bg-blue-500/10 text-blue-500",
      border: "border-blue-500/20"
    },
    {
      icon: Shield,
      title: "Fortress Privacy",
      description: "Your data is yours alone. We use military-grade encryption to ensure your sessions are secure.",
      color: "bg-green-500/10 text-green-500",
      border: "border-green-500/20"
    },
    {
      icon: Sparkles,
      title: "Scientific Foundation",
      description: "Built on proven CBT and mindfulness techniques, guided by mental health professionals.",
      color: "bg-purple-500/10 text-purple-500",
      border: "border-purple-500/20"
    },
    {
      icon: Users,
      title: "Global Community",
      description: "Join thousands of others finding their path to peace with ELLA by their side.",
      color: "bg-orange-500/10 text-orange-500",
      border: "border-orange-500/20"
    }
  ];

  return (
    <div className="min-h-screen bg-[#fcfdff] dark:bg-[#0a0d14] selection:bg-primary/30 font-sans overflow-x-hidden">
      <Navigation />

      {/* Hero Section with Parallax */}
      <section ref={targetRef} className="relative h-[90vh] flex items-center justify-center overflow-hidden">
        <motion.div style={{ opacity, scale, y }} className="container mx-auto px-4 z-10 text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 1 }}
            className="mb-6 flex justify-center"
          >
            <Badge variant="outline" className="py-1.5 px-4 bg-white/50 dark:bg-white/5 backdrop-blur-md border-primary/20 text-primary">
              <Sparkles className="w-3.5 h-3.5 mr-2" />
              The Future of Mental Wellness
            </Badge>
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="text-6xl md:text-8xl font-bold mb-8 tracking-tight text-slate-900 dark:text-white"
          >
            Human Heart.<br />
            <span className="bg-gradient-to-r from-primary via-secondary to-primary bg-[length:200%_auto] animate-gradient-x bg-clip-text text-transparent">
              AI Intelligence.
            </span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="text-xl text-slate-500 dark:text-slate-400 max-w-2xl mx-auto leading-relaxed mb-10"
          >
            We're building ELLA to ensure that no one has to face their darkest moments alone.
            Compassionate, accessible, and always here for you.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.6 }}
            className="flex flex-wrap justify-center gap-4"
          >
            <Button size="lg" onClick={() => navigate('/auth')} className="h-14 px-8 rounded-2xl bg-primary hover:bg-primary/90 text-white shadow-xl shadow-primary/20 transition-all group">
              Start Your Journey
              <ArrowRight className="ml-2 w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Button>
            <Button
              variant="outline"
              size="lg"
              onClick={() => {
                const el = document.getElementById('meet-developers');
                el?.scrollIntoView({ behavior: 'smooth' });
              }}
              className="h-14 px-8 rounded-2xl bg-white/50 backdrop-blur-md border-slate-200"
            >
              Meet the Developers
            </Button>
          </motion.div>
        </motion.div>

        {/* Dynamic Background Elements */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full -z-10 bg-[radial-gradient(circle_at_center,rgba(124,58,237,0.05)_0%,transparent_70%)]" />
      </section>

      {/* Philosophy Section */}
      <section className="py-32 relative">
        <div className="container mx-auto px-4 max-w-6xl">
          <div className="grid lg:grid-cols-2 gap-20 items-center">
            <FadeInWhenVisible>
              <div className="relative">
                <div className="absolute -top-10 -left-10 w-40 h-40 bg-primary/10 rounded-full blur-3xl" />
                <Badge variant="outline" className="mb-4 text-primary border-primary/20">OUR PHILOSOPHY</Badge>
                <h2 className="text-4xl md:text-5xl font-bold mb-6 text-slate-900 dark:text-white leading-tight">
                  Support that scales with your <span className="text-primary italic">needs.</span>
                </h2>
                <p className="text-lg text-slate-500 dark:text-slate-400 mb-8 leading-relaxed">
                  Traditional therapy is often expensive and restricted by office hours. ELLA removes these barriers, offering
                  a supportive ear that's available at 3 AM just as easily as 3 PM. We combine neural computing with
                  psychological frameworks to deliver a unique healing experience.
                </p>
                <div className="space-y-4">
                  {[
                    "Zero judgment, 100% acceptance",
                    "Immediate emotional crisis support",
                    "Data-driven mood tracking & analysis",
                    "Seamless cross-device experience"
                  ].map((text, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                        <CheckCircle className="w-3 h-3 text-primary" />
                      </div>
                      <span className="text-slate-700 dark:text-slate-300 font-medium">{text}</span>
                    </div>
                  ))}
                </div>
              </div>
            </FadeInWhenVisible>

            <FadeInWhenVisible delay={0.2}>
              <div className="grid grid-cols-2 gap-6">
                {features.map((feature, i) => (
                  <motion.div
                    key={i}
                    whileHover={{ y: -8, scale: 1.02 }}
                    className={`p-8 rounded-[32px] border ${feature.border} bg-white dark:bg-white/5 shadow-xl shadow-slate-200/40 dark:shadow-none transition-all duration-300`}
                  >
                    <div className={`w-14 h-14 rounded-2xl ${feature.color} flex items-center justify-center mb-6`}>
                      <feature.icon className="w-7 h-7" />
                    </div>
                    <h3 className="text-xl font-bold mb-3 text-slate-900 dark:text-white">{feature.title}</h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">{feature.description}</p>
                  </motion.div>
                ))}
              </div>
            </FadeInWhenVisible>
          </div>
        </div>
      </section>

      {/* Impact Stats */}
      <section className="py-24 bg-slate-900 border-y border-white/5">
        <div className="container mx-auto px-4 max-w-6xl">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-12 text-center">
            {[
              { val: "24/7", label: "Availability", icon: Clock },
              { val: "100%", label: "Privacy Secure", icon: Lock },
              { val: "0", label: "Judgment", icon: Heart },
              { val: "Infinite", label: "Conversations", icon: MessageCircle }
            ].map((stat, i) => (
              <FadeInWhenVisible key={i} delay={i * 0.1}>
                <div className="group">
                  <stat.icon className="w-8 h-8 text-primary/50 mx-auto mb-4 transition-colors group-hover:text-primary" />
                  <div className="text-4xl font-bold text-white mb-2">{stat.val}</div>
                  <div className="text-slate-400 font-medium uppercase tracking-[0.2em] text-xs leading-relaxed">{stat.label}</div>
                </div>
              </FadeInWhenVisible>
            ))}
          </div>
        </div>
      </section>

      {/* Meet the Developers */}
      <section id="meet-developers" className="py-32 relative">
        <div className="container mx-auto px-4 max-w-6xl">
          <FadeInWhenVisible>
            <div className="text-center mb-16">
              <Badge variant="outline" className="mb-4 text-primary border-primary/20">MEET THE TEAM</Badge>
              <h2 className="text-4xl md:text-5xl font-bold mb-4 text-slate-900 dark:text-white leading-tight">
                The minds behind <span className="text-primary italic">ELLA</span>.
              </h2>
              <p className="text-lg text-slate-500 dark:text-slate-400 max-w-2xl mx-auto">
                Three developers, one mission — making compassionate support accessible for everyone.
              </p>
            </div>
          </FadeInWhenVisible>

          <div className="grid md:grid-cols-3 gap-6 items-stretch">
            {[
              {
                name: "AttaUrRehman",
                role: "BACKEND & ML ENGINEER",
                emoji: "🛠️",
                quote: "Great engineering disappears. My job is to make sure ELLA just works — at 3 AM, at scale, every time someone needs her.",
                background: "Computer Science at GIKI",
                focus: "Backend & ML Pipelines",
                github: "https://github.com/AttaUrRehman",
                linkedin: "https://www.linkedin.com/in/attaurrehman/",
              },
              {
                name: "Muhammad Abdullah Farid",
                role: "PROJECT LEAD & FULL STACK ENGINEER",
                emoji: "🧑‍💻",
                quote: "We built ELLA for everyone who's ever wanted to talk at an hour when no one was awake. Empathy is the feature; the code is just the delivery.",
                background: "Computer Science at GIKI",
                focus: "Product, Full Stack & Clinical UX",
                github: "https://github.com/MuhammadAbdullahFarid",
                linkedin: "https://www.linkedin.com/in/muhammad-abdullah-farid/",
                featured: true,
              },
              {
                name: "Abdullah Mansoor",
                role: "SOFTWARE ARCHITECT & AI RESEARCHER",
                emoji: "👨‍💻",
                quote: "I believe technology should serve our humanity, not replace it. ELLA is my contribution to making the world a slightly more empathetic place, one conversation at a time.",
                background: "Computer Science at GIKI",
                focus: "Full Stack & AI Systems",
                github: "https://github.com/NOOBBoy35",
                linkedin: "https://www.linkedin.com/in/abdullah-mansoor-a9a424218/",
              },
            ].map((dev, i) => (
              <FadeInWhenVisible key={dev.name} delay={i * 0.1}>
                <motion.div
                  whileHover={{ y: -8 }}
                  className={`h-full bg-white/95 dark:bg-[#0f1117]/95 backdrop-blur-2xl border rounded-[32px] p-8 shadow-2xl transition-all ${dev.featured ? 'border-primary/40 ring-2 ring-primary/20 md:scale-[1.03]' : 'border-white/20 dark:border-white/10'}`}
                >
                  <div className="flex flex-col items-center text-center space-y-6 h-full">
                    <div className="w-24 h-24 rounded-3xl bg-gradient-to-tr from-primary to-secondary p-[2px]">
                      <div className="w-full h-full rounded-[22px] bg-white dark:bg-[#0a0d14] flex items-center justify-center text-4xl">
                        {dev.emoji}
                      </div>
                    </div>
                    <div>
                      <h3 className="text-2xl font-bold mb-1 text-slate-900 dark:text-white">{dev.name}</h3>
                      <p className="text-primary font-medium tracking-wide text-sm">{dev.role}</p>
                    </div>
                    <Separator className="w-24 bg-primary/20" />
                    <p className="text-slate-600 dark:text-slate-400 leading-relaxed italic text-sm flex-1">
                      "{dev.quote}"
                    </p>
                    <div className="grid grid-cols-2 gap-3 w-full">
                      <div className="bg-slate-50 dark:bg-white/5 p-4 rounded-2xl border border-slate-100 dark:border-white/10 text-left">
                        <Code2 className="w-5 h-5 text-primary mb-2" />
                        <p className="text-xs font-bold uppercase text-slate-400 mb-1">Background</p>
                        <p className="text-sm font-medium">{dev.background}</p>
                      </div>
                      <div className="bg-slate-50 dark:bg-white/5 p-4 rounded-2xl border border-slate-100 dark:border-white/10 text-left">
                        <Zap className="w-5 h-5 text-secondary mb-2" />
                        <p className="text-xs font-bold uppercase text-slate-400 mb-1">Focus</p>
                        <p className="text-sm font-medium">{dev.focus}</p>
                      </div>
                    </div>
                    <div className="flex gap-3 w-full pt-2">
                      <Button
                        variant="outline"
                        className="flex-1 h-12 rounded-xl group"
                        onClick={() => window.open(dev.github, '_blank')}
                      >
                        <Github className="w-4 h-4 mr-2" />
                        GitHub
                      </Button>
                      <Button
                        className="flex-1 h-12 rounded-xl bg-[#0077b5] hover:bg-[#0077b5]/90 text-white border-0"
                        onClick={() => window.open(dev.linkedin, '_blank')}
                      >
                        <Linkedin className="w-4 h-4 mr-2" />
                        LinkedIn
                      </Button>
                    </div>
                  </div>
                </motion.div>
              </FadeInWhenVisible>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-40 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-full bg-[radial-gradient(ellipse_at_top,rgba(124,58,237,0.1)_0%,transparent_50%)]" />
        <div className="container mx-auto px-4 max-w-4xl relative z-10">
          <FadeInWhenVisible>
            <Card className="rounded-[48px] bg-gradient-to-br from-white to-slate-50 dark:from-white/5 dark:to-white/10 border-white/20 p-12 md:p-20 text-center shadow-3xl">
              <div className="inline-flex items-center justify-center w-20 h-20 bg-primary/20 rounded-full mb-10">
                <Heart className="w-10 h-10 text-primary animate-pulse" />
              </div>
              <h2 className="text-4xl md:text-5xl font-bold mb-8 text-slate-900 dark:text-white leading-tight">
                Ready to take the first step towards emotional clarity?
              </h2>
              <p className="text-lg text-slate-500 dark:text-slate-400 mb-12 max-w-xl mx-auto">
                Join our community and discover why thousands trust ELLA as their primary source of
                mental wellness support.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-6">
                <Button size="lg" onClick={() => navigate('/auth')} className="h-16 px-10 rounded-2xl bg-primary text-white text-lg font-semibold shadow-2xl shadow-primary/30 transition-all hover:scale-105">
                  Begin Free Session
                </Button>
                <Button variant="ghost" className="h-16 px-8 text-slate-500 hover:text-primary transition-colors flex items-center gap-2">
                  <Coffee className="w-5 h-5" />
                  Support our mission
                </Button>
              </div>
            </Card>
          </FadeInWhenVisible>
        </div>
      </section>

      {/* Elegant Footer */}
      <footer className="py-12 border-t border-slate-100 dark:border-white/5">
        <div className="container mx-auto px-4 text-center">
          <div className="flex items-center justify-center gap-2 mb-6">
            <Brain className="w-6 h-6 text-primary/50" />
            <span className="text-lg font-bold tracking-tight text-slate-400">ELLA</span>
          </div>
          <p className="text-slate-400 text-sm font-medium">
            &copy; 2024 ELLA Mental Wellness. Built with ❤️ for humanity.
          </p>
        </div>
      </footer>

      <MobileNavigation />
    </div >
  );
}