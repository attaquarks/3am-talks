import React, { useState } from 'react';
import BackgroundDecor from '@/components/auth/BackgroundDecor';
import LoginCard from '@/components/auth/LoginCard';
import QuickSupport from '@/components/auth/QuickSupport';
import { Wind, X, Mail, Lock, LogIn, ChevronRight, Sparkles, Stethoscope, BadgeCheck, Users, ClipboardList } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { Link, useLocation } from 'react-router-dom';

type AuthRole = 'patient' | 'therapist';

const Auth: React.FC = () => {
  const [showHowItWorks, setShowHowItWorks] = useState(false);
  const location = useLocation();
  const initialRole: AuthRole = location.pathname === '/auth/therapist' ? 'therapist' : 'patient';
  const [role, setRole] = useState<AuthRole>(initialRole);
  const isTherapist = role === 'therapist';

  return (
    <div className="min-h-screen relative flex flex-col items-center bg-gradient-to-br from-primary/10 via-background to-secondary/10 selection:bg-primary/30 overflow-x-hidden">
      <BackgroundDecor />

      {/* Navigation / Header */}
      <motion.nav
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="w-full px-8 py-10 flex justify-between items-center max-w-7xl z-20"
      >
        <div className="flex items-center gap-4 group cursor-pointer" onClick={() => window.location.href = '/'}>
          <div className="relative w-12 h-12 flex items-center justify-center">
            <Wind className="absolute text-primary/40 group-hover:rotate-12 transition-all" size={38} strokeWidth={1.5} />
            <Sparkles className="absolute text-accent/60 -top-1 -right-1 animate-pulse" size={18} />
          </div>
          <span className="flex flex-col leading-tight">
            <span className="text-3xl font-light tracking-[0.2em] uppercase">
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-secondary to-accent">Ella AI</span>
            </span>
            <span className="text-[9px] uppercase tracking-[0.35em] text-muted-foreground/70 mt-1">by 3AM Talks</span>
          </span>
        </div>

        <div className="flex items-center gap-6">
          <Link
            to="/learn-more"
            className="hidden md:block text-[10px] font-black uppercase tracking-[0.2em] text-foreground/40 hover:text-primary transition-colors"
          >
            Learn More
          </Link>
          <button
            onClick={() => setShowHowItWorks(true)}
            className="px-7 py-3 rounded-2xl bg-card text-[10px] font-black uppercase tracking-[0.2em] text-foreground/60 hover:bg-card/80 transition-all border border-border hover:shadow-xl shadow-primary/10 active:scale-95"
          >
            How it Works
          </button>
        </div>
      </motion.nav>

      {/* Main Content */}
      <main className="flex-1 w-full flex flex-col items-center justify-center px-8 py-12 max-w-7xl z-10">
        <div className="flex flex-col md:flex-row items-center justify-between w-full gap-20">

          {/* Value Proposition Section */}
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="flex-1 max-w-xl text-center md:text-left"
          >
            <AnimatePresence mode="wait">
              {isTherapist ? (
                <motion.div
                  key="therapist-info"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  transition={{ duration: 0.35 }}
                >
                  <div className="inline-flex items-center gap-3 px-5 py-2.5 rounded-full bg-card border border-secondary/30 text-secondary-foreground text-[10px] font-black uppercase tracking-[0.2em] mb-10 shadow-xl shadow-secondary/10">
                    <Stethoscope className="w-3.5 h-3.5 text-secondary-foreground" />
                    Clinician Network
                  </div>

                  <h2 className="text-5xl md:text-7xl font-black text-foreground leading-[1.05] mb-10 tracking-tighter">
                    Care for your <br />
                    <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-secondary to-accent">patients, smarter.</span>
                  </h2>

                  <div className="space-y-8">
                    <div className="flex items-start gap-6 group">
                      <div className="w-14 h-14 shrink-0 rounded-[1.5rem] bg-card flex items-center justify-center text-primary shadow-xl border border-border group-hover:scale-110 transition-transform">
                        <Users className="w-7 h-7" />
                      </div>
                      <div>
                        <h4 className="font-black text-foreground uppercase text-xs tracking-widest mb-2">Context-Rich Caseload</h4>
                        <p className="text-muted-foreground text-sm font-medium leading-relaxed max-w-sm">See mood trends, session history, and AI-generated SOAP summaries — with the patient's explicit consent, always.</p>
                      </div>
                    </div>

                    <div className="flex items-start gap-6 group">
                      <div className="w-14 h-14 shrink-0 rounded-[1.5rem] bg-card flex items-center justify-center text-primary shadow-xl border border-border group-hover:scale-110 transition-transform">
                        <ClipboardList className="w-7 h-7" />
                      </div>
                      <div>
                        <h4 className="font-black text-foreground uppercase text-xs tracking-widest mb-2">Clinical Tooling</h4>
                        <p className="text-muted-foreground text-sm font-medium leading-relaxed max-w-sm">Private notes, treatment plans, between-session homework, secure messaging, and one-click crisis escalation.</p>
                      </div>
                    </div>

                    <div className="flex items-start gap-6 group">
                      <div className="w-14 h-14 shrink-0 rounded-[1.5rem] bg-card flex items-center justify-center text-primary shadow-xl border border-border group-hover:scale-110 transition-transform">
                        <BadgeCheck className="w-7 h-7" />
                      </div>
                      <div>
                        <h4 className="font-black text-foreground uppercase text-xs tracking-widest mb-2">License Verified</h4>
                        <p className="text-muted-foreground text-sm font-medium leading-relaxed max-w-sm">Every clinician is reviewed by our team before portal access is granted. Trust, verified.</p>
                      </div>
                    </div>
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key="patient-info"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  transition={{ duration: 0.35 }}
                >
                  <div className="inline-flex items-center gap-3 px-5 py-2.5 rounded-full bg-card border border-primary/20 text-primary text-[10px] font-black uppercase tracking-[0.2em] mb-10 shadow-xl shadow-primary/10">
                    <span className="relative flex h-2.5 w-2.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary/40 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-primary"></span>
                    </span>
                    Presence Indicated
                  </div>

                  <h2 className="text-5xl md:text-7xl font-black text-foreground leading-[1.05] mb-10 tracking-tighter">
                    Your path to <br />
                    <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-secondary to-accent">emotional clarity</span> <br />
                    starts here.
                  </h2>

                  <div className="space-y-8">
                    <div className="flex items-start gap-6 group">
                      <div className="w-14 h-14 shrink-0 rounded-[1.5rem] bg-card flex items-center justify-center text-primary shadow-xl border border-border group-hover:scale-110 transition-transform">
                        <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
                      </div>
                      <div>
                        <h4 className="font-black text-foreground uppercase text-xs tracking-widest mb-2">Private Sanctuary</h4>
                        <p className="text-muted-foreground text-sm font-medium leading-relaxed max-w-sm">Military-grade encryption ensures your thoughts and sessions are kept completely confidential.</p>
                      </div>
                    </div>

                    <div className="flex items-start gap-6 group">
                      <div className="w-14 h-14 shrink-0 rounded-[1.5rem] bg-card flex items-center justify-center text-primary shadow-xl border border-border group-hover:scale-110 transition-transform">
                        <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"></path></svg>
                      </div>
                      <div>
                        <h4 className="font-black text-foreground uppercase text-xs tracking-widest mb-2">Resonant AI</h4>
                        <p className="text-muted-foreground text-sm font-medium leading-relaxed max-w-sm">Built on validated psychological models to provide genuine, compassionate emotional support.</p>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>

          {/* Login Card Section */}
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.4 }}
            className="flex-1 w-full max-w-lg"
          >
            <LoginCard initialRole={initialRole} onRoleChange={setRole} />
          </motion.div>
        </div>
      </main>

      {/* Simplified Footer */}
      <motion.footer
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
        className="w-full px-12 py-12 mt-20 border-t border-border bg-transparent"
      >
        <div className="max-w-7xl mx-auto flex flex-col items-center">
          <p className="text-foreground/40 text-[9px] font-bold uppercase tracking-[0.5em] text-center">
            © 2026 3AM TALKS · ELLA AI · AI MENTAL HEALTH ASSISTANT
          </p>
        </div>
      </motion.footer>

      {/* Quick AI Support Widget */}
      <QuickSupport />

      {/* How it Works Modal */}
      <AnimatePresence>
        {showHowItWorks && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 md:p-12">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowHowItWorks(false)}
              className="absolute inset-0 bg-background/40 backdrop-blur-xl"
            />

            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="relative w-full max-w-4xl bg-card/60 backdrop-blur-2xl border border-white/40 rounded-[3rem] p-10 md:p-16 shadow-2xl overflow-hidden"
            >
              <div className="relative z-10">
                <div className="flex justify-between items-center mb-16">
                  <div>
                    <h3 className="text-[10px] font-black uppercase tracking-[0.4em] text-primary mb-3">The Path</h3>
                    <h2 className="text-4xl md:text-5xl font-black text-foreground tracking-tighter">Your Journey Begins</h2>
                  </div>
                  <button
                    onClick={() => setShowHowItWorks(false)}
                    className="w-14 h-14 rounded-2xl bg-white/40 hover:bg-white/60 border border-white flex items-center justify-center text-foreground/40 hover:text-foreground transition-all active:scale-90"
                  >
                    <X size={24} />
                  </button>
                </div>

                <div className="grid md:grid-cols-3 gap-8">
                  {[
                    {
                      step: "01",
                      title: "Identity",
                      description: "Enter your secure email address to access your personal space.",
                      icon: Mail,
                      color: "text-sky-400",
                      bg: "bg-sky-50"
                    },
                    {
                      step: "02",
                      title: "Security",
                      description: "Provide your secret key. We use military-grade encryption.",
                      icon: Lock,
                      color: "text-purple-400",
                      bg: "bg-purple-50"
                    },
                    {
                      step: "03",
                      title: "Presence",
                      description: "Step inside your sanctuary and begin your path to clarity.",
                      icon: LogIn,
                      color: "text-emerald-400",
                      bg: "bg-emerald-50"
                    }
                  ].map((item, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.1 * idx }}
                      className="group relative p-8 rounded-[2rem] bg-card border border-border transition-all hover:shadow-2xl hover:shadow-primary/5 cursor-default hover:-translate-y-2"
                    >
                      <div className="flex justify-between items-start mb-8">
                        <div className={cn("w-14 h-14 rounded-2xl flex items-center justify-center shadow-lg transition-transform group-hover:rotate-6", item.bg, item.color)}>
                          <item.icon size={26} />
                        </div>
                        <span className="text-xl font-black text-foreground/10 group-hover:text-primary/20 transition-colors uppercase italic">{item.step}</span>
                      </div>
                      <h4 className="text-[10px] font-black text-foreground uppercase tracking-[0.2em] mb-3">{item.title}</h4>
                      <p className="text-sm font-medium text-foreground/60 leading-relaxed">{item.description}</p>

                      {idx < 2 && (
                        <div className="hidden md:block absolute -right-4 top-1/2 -translate-y-1/2 z-20">
                          <ChevronRight className="text-foreground/20 group-hover:translate-x-1 group-hover:text-primary transition-all" size={24} />
                        </div>
                      )}
                    </motion.div>
                  ))}
                </div>

                <div className="mt-16 text-center">
                  <button
                    onClick={() => setShowHowItWorks(false)}
                    className="px-12 py-5 rounded-[1.5rem] bg-primary text-primary-foreground font-black uppercase tracking-[0.2em] text-sm shadow-xl shadow-primary/20 hover:scale-105 active:scale-95 transition-all"
                  >
                    I'm Ready to Enter
                  </button>
                  <div className="mt-8">
                    <Link
                      to="/learn-more"
                      className="text-[10px] font-black uppercase tracking-[0.2em] text-foreground/30 hover:text-primary transition-colors"
                    >
                      Learn more about our mission
                    </Link>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default Auth;