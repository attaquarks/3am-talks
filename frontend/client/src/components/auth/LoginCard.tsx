import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthMode } from '@/types/auth';
import { Mail, Lock, User, ArrowRight, Chrome, Facebook, Loader2, Sparkles } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/use-toast';
import { getSupabaseBrowser } from '@/lib/supabaseBrowser';
import { motion, AnimatePresence } from 'framer-motion';

const LoginCard: React.FC = () => {
    const { refetchUser } = useAuth();
    const [mode, setMode] = useState<AuthMode>(AuthMode.LOGIN);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [name, setName] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const { toast } = useToast();
    const navigate = useNavigate();

    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const oauthError = params.get('oauth_error');
        if (oauthError) {
            toast({ title: "Login failed", description: oauthError, variant: "destructive" });
            params.delete('oauth_error');
            const next = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ''}`;
            window.history.replaceState({}, '', next);
        }
    }, [toast]);

    const handleAuth = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);

        const endpoint = mode === AuthMode.SIGNUP ? '/api/register' : '/api/login';
        const payload = mode === AuthMode.SIGNUP
            ? { email, password, name }
            : { email, password };

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Authentication failed');
            }

            await refetchUser();
            
            if (mode === AuthMode.SIGNUP) {
                toast({ title: "Welcome to 3AM!", description: "Account created successfully." });
            } else {
                toast({ title: "Welcome back!", description: "Logged in successfully." });
            }
            navigate('/dashboard');
        } catch (error: any) {
            toast({ title: "Error", description: error.message, variant: "destructive" });
        } finally {
            setIsLoading(false);
        }
    };

    const handleSocialLogin = async (provider: 'google' | 'facebook') => {
        try {
            const supabase = getSupabaseBrowser();
            const { error } = await supabase.auth.signInWithOAuth({
                provider,
                options: { redirectTo: `${window.location.origin}/auth/oauth-success` },
            });
            if (error) {
                toast({ title: 'Login failed', description: error.message, variant: 'destructive' });
            }
        } catch (e: any) {
            toast({
                title: 'Login failed',
                description: e?.message ?? 'OAuth is not configured.',
                variant: 'destructive',
            });
        }
    };

    const handleDemoLogin = async () => {
        toast({
            title: "Demo Login Disabled",
            description: "Demo account shortcuts are disabled in production mode.",
            variant: "destructive",
        });
    };

    return (
        <div className="w-full max-w-md mx-auto">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="bg-card backdrop-blur-md rounded-[3rem] p-10 md:p-14 shadow-shadow-lg border border-border relative overflow-hidden"
            >
                {/* Abstract AI Sparkle Decor */}
                <div className="absolute top-0 right-0 p-6">
                    <motion.div
                        animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.6, 0.3] }}
                        transition={{ duration: 4, repeat: Infinity }}
                        className="w-32 h-32 bg-primary/20 rounded-full blur-3xl"
                    />
                </div>

                <div className="text-center mb-12 relative z-10">
                    <motion.div
                        whileHover={{ scale: 1.1, rotate: 10 }}
                        className="inline-block p-5 rounded-[2rem] bg-white/60 mb-8 shadow-xl shadow-primary/10 border border-white/80 transition-all"
                    >
                        <svg className="w-14 h-14 text-primary" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM12 20C7.59 20 4 16.41 4 12C4 7.59 7.59 4 12 4C16.41 4 20 7.59 20 12C20 16.41 16.41 20 12 20Z" fill="currentColor" />
                            <path opacity="0.4" d="M12 17C14.7614 17 17 14.7614 17 12C17 9.23858 14.7614 7 12 7C9.23858 7 7 9.23858 7 12C7 14.7614 9.23858 17 12 17Z" fill="currentColor" />
                            <path d="M12 14C13.1046 14 14 13.1046 14 12C14 10.8954 13.1046 10 12 10C10.8954 10 10 10.8954 10 12C10 13.1046 10.8954 14 12 14Z" fill="currentColor" />
                        </svg>
                    </motion.div>

                    <AnimatePresence mode="wait">
                        <motion.div
                            key={mode}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            transition={{ duration: 0.3 }}
                        >
                            <h1 className="text-4xl font-black text-foreground tracking-tight mb-4">
                                {mode === AuthMode.LOGIN ? 'Welcome' : 'Join ELLA'}
                            </h1>
                            <p className="text-foreground/80 font-medium leading-relaxed max-w-[280px] mx-auto text-sm">
                                {mode === AuthMode.LOGIN
                                    ? "Your sanctuary awaits. Step inside."
                                    : "Begin your journey to clarity with support."}
                            </p>
                        </motion.div>
                    </AnimatePresence>
                </div>

                <form onSubmit={handleAuth} className="space-y-5 relative z-10">
                    <AnimatePresence mode="sync">
                        {mode === AuthMode.SIGNUP && (
                            <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                className="group"
                            >
                                <label className="block text-[10px] font-bold text-foreground/60 uppercase tracking-widest ml-4 mb-2">Name</label>
                                <div className="relative">
                                    <User className="absolute left-5 top-1/2 -translate-y-1/2 text-foreground/50 group-focus-within:text-primary transition-colors" size={18} />
                                    <input
                                        type="text"
                                        required={mode === AuthMode.SIGNUP}
                                        value={name}
                                        onChange={(e) => setName(e.target.value)}
                                        placeholder="How should we call you?"
                                        className="w-full bg-background border border-border rounded-2xl py-4.5 pl-14 pr-6 focus:outline-none focus:ring-4 focus:ring-primary/20 transition-all text-foreground placeholder:text-foreground/50 shadow-sm"
                                    />
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    <div className="group">
                        <label className="block text-[10px] font-bold text-foreground/60 uppercase tracking-widest ml-4 mb-2">Email</label>
                        <div className="relative">
                            <Mail className="absolute left-5 top-1/2 -translate-y-1/2 text-foreground/50 group-focus-within:text-primary transition-colors" size={18} />
                            <input
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="Ex: hello@peace.com"
                                className="w-full bg-background border border-border rounded-2xl py-4.5 pl-14 pr-6 focus:outline-none focus:ring-4 focus:ring-primary/20 transition-all text-foreground placeholder:text-foreground/50 shadow-sm"
                                required
                            />
                        </div>
                    </div>

                    <div className="group">
                        <div className="flex justify-between items-center px-4 mb-2">
                            <label className="text-[10px] font-bold text-foreground/60 uppercase tracking-widest">Secret</label>
                            {mode === AuthMode.LOGIN && (
                                <button type="button" className="text-[10px] font-bold text-primary hover:text-primary/80 uppercase tracking-widest">Forgot?</button>
                            )}
                        </div>
                        <div className="relative">
                            <Lock className="absolute left-5 top-1/2 -translate-y-1/2 text-foreground/50 group-focus-within:text-primary transition-colors" size={18} />
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="••••••••"
                                className="w-full bg-background border border-border rounded-2xl py-4.5 pl-14 pr-6 focus:outline-none focus:ring-4 focus:ring-primary/20 transition-all text-foreground placeholder:text-foreground/50 shadow-sm"
                                required
                                minLength={6}
                            />
                        </div>
                    </div>

                    <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="pt-4">
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-bold py-5 rounded-[1.5rem] shadow-2xl shadow-primary/20 transition-all flex items-center justify-center gap-3 group disabled:opacity-70"
                        >
                            {isLoading ? (
                                <Loader2 className="h-6 w-6 animate-spin" />
                            ) : (
                                <>
                                    <span className="tracking-widest uppercase text-sm">
                                        {mode === AuthMode.LOGIN ? 'Step Inside' : 'Create Space'}
                                    </span>
                                    <ArrowRight size={20} className="group-hover:translate-x-1 transition-transform" />
                                </>
                            )}
                        </button>
                    </motion.div>
                </form>

                <div className="mt-10 mb-8 px-4">
                    <div className="relative flex items-center justify-center">
                        <div className="absolute inset-0 flex items-center">
                            <div className="w-full border-t border-border/10"></div>
                        </div>
                        <span className="relative bg-white/0 px-4 text-[9px] font-bold text-slate-400 uppercase tracking-[0.2em] backdrop-blur-sm">Aura Connect</span>
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4 relative z-10">
                    <button
                        type="button"
                        onClick={() => handleSocialLogin('google')}
                        className="flex items-center justify-center gap-3 bg-background hover:bg-muted border border-border py-4 rounded-2xl transition-all hover:shadow-lg shadow-primary/5 active:scale-95"
                    >
                        <Chrome size={18} className="text-rose-400" />
                        <span className="text-xs font-bold text-foreground/80 uppercase tracking-widest">Google</span>
                    </button>
                    <button
                        type="button"
                        onClick={() => handleSocialLogin('facebook')}
                        className="flex items-center justify-center gap-3 bg-background hover:bg-muted border border-border py-4 rounded-2xl transition-all hover:shadow-lg shadow-primary/5 active:scale-95"
                    >
                        <Facebook size={18} className="text-foreground" />
                        <span className="text-xs font-bold text-foreground/80 uppercase tracking-widest">Facebook</span>
                    </button>
                </div>

                <div className="mt-4 relative z-10">
                    <button
                        type="button"
                        onClick={handleDemoLogin}
                        disabled={isLoading}
                        className="w-full flex items-center justify-center gap-3 bg-primary/5 hover:bg-primary/10 border border-primary/20 py-4 rounded-2xl transition-all hover:shadow-lg shadow-primary/5 active:scale-95 disabled:opacity-50"
                    >
                        <Sparkles size={18} className="text-primary" />
                        <span className="text-xs font-bold text-primary uppercase tracking-widest">Try Demo Account</span>
                    </button>
                </div>

                <div className="mt-12 text-center relative z-10">
                    <p className="text-muted-foreground text-xs font-medium">
                        {mode === AuthMode.LOGIN ? "New Presence?" : "Already Connected?"}{' '}
                        <button
                            type="button"
                            onClick={() => setMode(mode === AuthMode.LOGIN ? AuthMode.SIGNUP : AuthMode.LOGIN)}
                            className="text-primary font-black hover:text-primary/80 transition-colors uppercase tracking-widest ml-1"
                        >
                            {mode === AuthMode.LOGIN ? 'Join ELLA' : 'Sign In'}
                        </button>
                    </p>
                </div>
            </motion.div>

            <p className="text-center mt-8 text-slate-400 text-[10px] font-bold uppercase tracking-[0.2em] max-w-[280px] mx-auto leading-loose opacity-60">
                Safe / Secure / Compassionate
            </p>
        </div>
    );
};

export default LoginCard;
