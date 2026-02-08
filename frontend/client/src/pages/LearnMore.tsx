import React from 'react';
import { motion } from 'framer-motion';
import { Wind, Users, Target, Shield, Rocket, Heart, ArrowLeft, Github, Linkedin, Instagram, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import BackgroundDecor from '@/components/auth/BackgroundDecor';

const LearnMore: React.FC = () => {
    const navigate = useNavigate();

    const team = [
        {
            name: "Abdullah Mansoor",
            role: "AI Ethics Lead",
            image: "https://picsum.photos/seed/sarah/400/400",
            bio: "Specializing in compassionate AI systems and emotional resonance.",
            socials: {
                github: "https://github.com/NOOBBoy35",
                linkedin: "https://www.linkedin.com/in/abdullah-mansoor-a9a424218",
                instagram: "https://www.instagram.com/abdullah._.35/"
            }
        },
        {
            name: "Atta Ur Rahman",
            role: "Software Architect",
            image: "https://picsum.photos/seed/marcus/400/400",
            bio: "Building secure, scalable sanctuaries for digital wellness.",
            socials: {
                github: "https://github.com/attaquarks",
                linkedin: "https://www.linkedin.com/in/attaurrehmann/",
                instagram: "https://www.instagram.com/attaceaser/"
            }
        },
        {
            name: "Abdullah Farid",
            role: "Clinical Advisor",
            image: "https://picsum.photos/seed/elena/400/400",
            bio: "Integrating psychological models with next-gen technology.",
            socials: {
                github: "https://github.com/AbdullahFarid1",
                linkedin: "https://www.linkedin.com/in/maf-abdullahfarid/",
                instagram: "https://www.instagram.com/abdullahxfarid/"
            }
        }
    ];

    const priorities = [
        {
            title: "Absolute Privacy",
            description: "Your data is encrypted end-to-end. We never sell your thoughts.",
            icon: Shield,
            color: "text-primary"
        },
        {
            title: "Radical Empathy",
            description: "AI that doesn't just process words, but understands human feeling.",
            icon: Heart,
            color: "text-secondary"
        },
        {
            title: "Accessible Support",
            description: "Mental wellness shouldn't be a luxury. ELLA is for everyone.",
            icon: Rocket,
            color: "text-accent"
        }
    ];

    return (
        <div className="min-h-screen relative flex flex-col items-center bg-gradient-to-br from-primary/10 via-background to-secondary/10 selection:bg-primary/30 overflow-x-hidden">
            <BackgroundDecor />

            {/* Navigation */}
            <motion.nav
                initial={{ y: -20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                className="w-full px-8 py-10 flex justify-between items-center max-w-7xl z-20"
            >
                <div className="flex items-center gap-4 group cursor-pointer" onClick={() => navigate('/')}>
                    <div className="relative w-12 h-12 flex items-center justify-center">
                        <Wind className="absolute text-primary/40 group-hover:rotate-12 transition-all" size={38} strokeWidth={1.5} />
                        <Sparkles className="absolute text-accent/60 -top-1 -right-1 animate-pulse" size={18} />
                    </div>
                    <span className="text-3xl font-light tracking-[0.2em] uppercase">
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-secondary to-accent">Ella AI</span>
                    </span>
                </div>

                <button
                    onClick={() => navigate('/auth')}
                    className="flex items-center gap-2 px-6 py-3 rounded-2xl bg-card text-[10px] font-black uppercase tracking-[0.2em] text-foreground/60 hover:bg-card/80 transition-all border border-border hover:shadow-xl"
                >
                    <ArrowLeft size={14} />
                    Back to Login
                </button>
            </motion.nav>

            {/* Hero Section */}
            <main className="flex-1 w-full max-w-7xl px-8 py-20 z-10">
                <motion.div
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-center mb-32"
                >
                    <div className="inline-flex items-center gap-3 px-5 py-2.5 rounded-full bg-card border border-primary/20 text-primary text-[10px] font-black uppercase tracking-[0.4em] mb-10 shadow-xl">
                        Our DNA
                    </div>
                    <h1 className="text-6xl md:text-8xl font-black text-foreground tracking-tighter leading-none mb-10">
                        Humanity <br />
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-secondary to-accent leading-normal">Digitally Refined.</span>
                    </h1>
                    <p className="text-lg text-foreground/60 max-w-2xl mx-auto font-medium leading-relaxed">
                        We started ELLA with a simple belief: that technology can be the most powerful tool for empathy ever created.
                    </p>
                </motion.div>

                {/* Mission Section */}
                <div className="grid md:grid-cols-2 gap-20 items-center mb-40">
                    <motion.div
                        initial={{ opacity: 0, x: -30 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true }}
                    >
                        <h2 className="text-4xl font-black text-foreground tracking-tighter mb-8">The Mission.</h2>
                        <div className="space-y-6 text-lg text-foreground/70 font-medium leading-relaxed">
                            <p>
                                In an increasingly disconnected world, ELLA provides a bridge back to emotional clarity. Our goal is to democratize mental wellness through compassionate artificial intelligence.
                            </p>
                            <p>
                                We're not building a replacement for humans; we're building a 24/7 sanctuary for your thoughts, accessible whenever the weight of the world feels too heavy.
                            </p>
                        </div>
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0, scale: 0.9 }}
                        whileInView={{ opacity: 1, scale: 1 }}
                        viewport={{ once: true }}
                        className="bg-card/40 backdrop-blur-xl rounded-[3rem] p-12 border border-white/20 shadow-2xl relative"
                    >
                        <div className="absolute top-0 right-0 p-10">
                            <Target className="w-20 h-20 text-primary opacity-20" />
                        </div>
                        <div className="relative z-10">
                            <h3 className="text-2xl font-black text-foreground mb-6 uppercase tracking-widest text-[14px]">Core Metrics</h3>
                            <div className="space-y-8">
                                <div className="flex items-center justify-between border-b border-border/10 pb-4">
                                    <span className="text-sm font-bold text-foreground/60 uppercase tracking-widest">Availability</span>
                                    <span className="text-2xl font-black text-primary">24/7/365</span>
                                </div>
                                <div className="flex items-center justify-between border-b border-border/10 pb-4">
                                    <span className="text-sm font-bold text-foreground/60 uppercase tracking-widest">Privacy level</span>
                                    <span className="text-2xl font-black text-secondary">MAXIMUM</span>
                                </div>
                                <div className="flex items-center justify-between pb-4">
                                    <span className="text-sm font-bold text-foreground/60 uppercase tracking-widest">Humanity</span>
                                    <span className="text-2xl font-black text-accent">INFUSED</span>
                                </div>
                            </div>
                        </div>
                    </motion.div>
                </div>

                {/* Priorities Grid */}
                <div className="grid md:grid-cols-3 gap-8 mb-40">
                    {priorities.map((item, idx) => (
                        <motion.div
                            key={idx}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: idx * 0.1 }}
                            className="bg-card rounded-[2.5rem] p-12 border border-border shadow-xl hover:-translate-y-2 transition-all group"
                        >
                            <div className={`${item.color} mb-8 transition-transform group-hover:scale-110 group-hover:rotate-6`}>
                                <item.icon size={40} />
                            </div>
                            <h4 className="text-xl font-black text-foreground uppercase tracking-widest mb-4">{item.title}</h4>
                            <p className="text-foreground/60 font-medium leading-relaxed">{item.description}</p>
                        </motion.div>
                    ))}
                </div>

                {/* Team Section */}
                <div className="mb-40">
                    <div className="text-center mb-20">
                        <h2 className="text-5xl font-black text-foreground tracking-tighter mb-4">The Architects.</h2>
                        <p className="text-foreground/50 uppercase tracking-[0.3em] font-bold text-[10px]">Visionaries behind the resonance</p>
                    </div>

                    <div className="grid md:grid-cols-3 gap-12">
                        {team.map((member, idx) => (
                            <motion.div
                                key={idx}
                                initial={{ opacity: 0, scale: 0.9 }}
                                whileInView={{ opacity: 1, scale: 1 }}
                                viewport={{ once: true }}
                                transition={{ delay: idx * 0.1 }}
                                className="group"
                            >
                                <div className="relative mb-8 rounded-[3rem] overflow-hidden aspect-square shadow-2xl group-hover:translate-x-2 group-hover:-translate-y-2 transition-transform duration-500">
                                    <img src={member.image} alt={member.name} className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" />
                                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-8">
                                        <div className="flex gap-4">
                                            {member.socials?.github && (
                                                <a href={member.socials.github} target="_blank" rel="noopener noreferrer">
                                                    <Github size={18} className="text-white hover:text-primary cursor-pointer transition-colors" />
                                                </a>
                                            )}
                                            {member.socials?.linkedin && (
                                                <a href={member.socials.linkedin} target="_blank" rel="noopener noreferrer">
                                                    <Linkedin size={18} className="text-white hover:text-secondary cursor-pointer transition-colors" />
                                                </a>
                                            )}
                                            {member.socials?.instagram && (
                                                <a href={member.socials.instagram} target="_blank" rel="noopener noreferrer">
                                                    <Instagram size={18} className="text-white hover:text-accent cursor-pointer transition-colors" />
                                                </a>
                                            )}
                                            {!member.socials && (
                                                <>
                                                    <Github size={18} className="text-white hover:text-primary cursor-pointer transition-colors" />
                                                    <Linkedin size={18} className="text-white hover:text-secondary cursor-pointer transition-colors" />
                                                    <Instagram size={18} className="text-white hover:text-accent cursor-pointer transition-colors" />
                                                </>
                                            )}
                                        </div>
                                    </div>
                                </div>
                                <h4 className="text-2xl font-black text-foreground mb-1">{member.name}</h4>
                                <p className="text-primary font-black uppercase text-[10px] tracking-[0.2em] mb-4">{member.role}</p>
                                <p className="text-sm font-medium text-foreground/60 leading-relaxed">{member.bio}</p>
                            </motion.div>
                        ))}
                    </div>
                </div>

                {/* Final CTA */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true }}
                    className="bg-card rounded-[4rem] p-20 text-center border border-border shadow-2xl relative overflow-hidden"
                >
                    <div className="absolute inset-0 bg-gradient-to-r from-primary/5 via-secondary/5 to-accent/5" />
                    <div className="relative z-10">
                        <h2 className="text-5xl md:text-6xl font-black text-foreground tracking-tighter mb-10 leading-none">
                            Help is one <br /> <span className="text-primary">heartbeat</span> away.
                        </h2>
                        <button
                            onClick={() => navigate('/auth')}
                            className="bg-primary hover:bg-primary/90 text-primary-foreground font-black px-12 py-5 rounded-2xl shadow-xl shadow-primary/20 hover:scale-105 active:scale-95 transition-all uppercase tracking-[0.2em] text-sm"
                        >
                            Step Inside Your Space
                        </button>
                    </div>
                </motion.div>
            </main>

            {/* Footer */}
            <footer className="w-full py-20 border-t border-border mt-20">
                <div className="max-w-7xl mx-auto px-8 flex flex-col items-center">
                    <p className="text-foreground/30 text-[9px] font-black uppercase tracking-[0.5em] text-center mb-10">
                        © 2024 ELLA AI. Engineering Compassion.
                    </p>
                    <div className="flex gap-6 opacity-20">
                        <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                        <div className="w-1.5 h-1.5 rounded-full bg-secondary" />
                        <div className="w-1.5 h-1.5 rounded-full bg-accent" />
                    </div>
                </div>
            </footer>
        </div>
    );
};

export default LearnMore;
