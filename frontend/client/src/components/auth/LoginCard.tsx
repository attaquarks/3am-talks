import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthMode } from '@/types/auth';
import { Mail, Lock, User, ArrowRight, Chrome, Facebook, Loader2, Sparkles, Stethoscope, Heart, BadgeCheck } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/use-toast';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';

type AuthRole = 'patient' | 'therapist';

interface LoginCardProps {
    onRoleChange?: (role: AuthRole) => void;
    initialRole?: AuthRole;
}

const LoginCard: React.FC<LoginCardProps> = ({ onRoleChange, initialRole = 'patient' }) => {
    const { refetchUser } = useAuth();
    const [role, setRoleState] = useState<AuthRole>(initialRole);
    const setRole = (r: AuthRole) => {
        setRoleState(r);
        onRoleChange?.(r);
    };
    const [mode, setMode] = useState<AuthMode>(AuthMode.LOGIN);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [name, setName] = useState('');
    // therapist-only fields
    const [licenseNumber, setLicenseNumber] = useState('');
    const [licenseJurisdiction, setLicenseJurisdiction] = useState('');
    const [specializations, setSpecializations] = useState('');
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

    const isTherapist = role === 'therapist';
    const isSignup = mode === AuthMode.SIGNUP;

    const handleAuth = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);

        try {
            let endpoint: string;
            let payload: Record<string, unknown>;

            if (isSignup) {
                if (isTherapist) {
                    endpoint = '/api/therapist/register';
                    payload = {
                        email,
                        password,
                        name,
                        license_number: licenseNumber,
                        license_jurisdiction: licenseJurisdiction,
                        specializations: specializations
                            .split(',')
                            .map((s) => s.trim())
                            .filter(Boolean),
                    };
                } else {
                    endpoint = '/api/register';
                    payload = { email, password, name };
                }
            } else {
                endpoint = '/api/login';
                payload = { email, password };
            }

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const message = errorData?.detail?.message || errorData?.detail || errorData?.message || 'Authentication failed';
                throw new Error(typeof message === 'string' ? message : 'Authentication failed');
            }

            const data = await response.json();

            if (isSignup && isTherapist) {
                toast({
                    title: "Application submitted",
                    description: "Your clinician account is pending verification. You'll be notified once approved.",
                });
            } else {
                toast({
                    title: "Success",
                    description: isSignup ? "Account created successfully!" : "Logged in successfully!",
                });
            }

            await refetchUser();
            const resolvedRole = data?.role;
            const status = data?.account_status;

            if (resolvedRole === 'admin') {
                navigate('/admin');
            } else if (resolvedRole === 'therapist') {
                navigate(status === 'pending_verification' ? '/therapist-portal/pending' : '/therapist-portal');
            } else {
                navigate('/dashboard');
            }
        } catch (error: any) {
            toast({ title: "Error", description: error.message, variant: "destructive" });
        } finally {
            setIsLoading(false);
        }
    };

    const handleSocialLogin = (provider: 'google' | 'facebook') => {
        // Full-page navigation to backend start route — backend sets the
        // oauth_nonce cookie and redirects to Supabase /authorize. This
        // keeps the CSRF-nonce guard working end-to-end.
        window.location.href = `/api/auth/oauth/${provider}/start`;
    };

    return (
        <div className="w-full max-w-md mx-auto">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="bg-card backdrop-blur-md rounded-[3rem] p-10 md:p-14 shadow-shadow-lg border border-border relative overflow-hidden"
            >
                <div className="absolute top-0 right-0 p-6">
                    <motion.div
                        animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.6, 0.3] }}
                        transition={{ duration: 4, repeat: Infinity }}
                        className={cn(
                            "w-32 h-32 rounded-full blur-3xl",
                            isTherapist ? "bg-secondary/20" : "bg-primary/20"
                        )}
                    />
                </div>

                {/* Role Toggle */}
                <div className="relative z-10 mb-10">
                    <div className="grid grid-cols-2 gap-2 p-1.5 bg-muted/60 rounded-2xl border border-border">
                        <button
                            type="button"
                            onClick={() => setRole('patient')}
                            className={cn(
                                "relative flex items-center justify-center gap-2 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all",
                                role === 'patient'
                                    ? 'bg-card shadow-md text-primary'
                                    : 'text-muted-foreground hover:text-foreground'
                            )}
                        >
                            <Heart size={14} />
                            <span>Seeking Support</span>
                        </button>
                        <button
                            type="button"
                            onClick={() => setRole('therapist')}
                            className={cn(
                                "relative flex items-center justify-center gap-2 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all",
                                role === 'therapist'
                                    ? 'bg-card shadow-md text-secondary-foreground'
                                    : 'text-muted-foreground hover:text-foreground'
                            )}
                        >
                            <Stethoscope size={14} />
                            <span>Clinician</span>
                        </button>
                    </div>
                </div>

                <div className="text-center mb-10 relative z-10">
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={`${role}-${mode}`}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            transition={{ duration: 0.3 }}
                        >
                            <h1 className="text-4xl font-black text-foreground tracking-tight mb-3">
                                {isTherapist
                                    ? (isSignup ? 'Clinician Access' : 'Clinician Portal')
                                    : (isSignup ? 'Join ELLA' : 'Welcome')}
                            </h1>
                            <p className="text-foreground/80 font-medium leading-relaxed max-w-[300px] mx-auto text-sm">
                                {isTherapist
                                    ? (isSignup
                                        ? 'Apply to join our clinician network. All applications are reviewed before approval.'
                                        : 'Sign in to your clinician portal.')
                                    : (isSignup
                                        ? 'Begin your journey to clarity with support.'
                                        : 'Your sanctuary awaits. Step inside.')}
                            </p>
                        </motion.div>
                    </AnimatePresence>
                </div>

                <form onSubmit={handleAuth} className="space-y-5 relative z-10">
                    <AnimatePresence mode="sync">
                        {isSignup && (
                            <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                className="group"
                            >
                                <label className="block text-[10px] font-bold text-foreground/60 uppercase tracking-widest ml-4 mb-2">
                                    {isTherapist ? 'Full Name & Credentials' : 'Name'}
                                </label>
                                <div className="relative">
                                    <User className="absolute left-5 top-1/2 -translate-y-1/2 text-foreground/50 group-focus-within:text-primary transition-colors" size={18} />
                                    <input
                                        type="text"
                                        required={isSignup}
                                        value={name}
                                        onChange={(e) => setName(e.target.value)}
                                        placeholder={isTherapist ? 'Dr. Jane Smith, PsyD' : 'How should we call you?'}
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
                                placeholder={isTherapist ? 'dr.you@clinic.com' : 'Ex: hello@peace.com'}
                                className="w-full bg-background border border-border rounded-2xl py-4.5 pl-14 pr-6 focus:outline-none focus:ring-4 focus:ring-primary/20 transition-all text-foreground placeholder:text-foreground/50 shadow-sm"
                                required
                            />
                        </div>
                    </div>

                    <div className="group">
                        <div className="flex justify-between items-center px-4 mb-2">
                            <label className="text-[10px] font-bold text-foreground/60 uppercase tracking-widest">Secret</label>
                            {!isSignup && (
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

                    <AnimatePresence mode="sync">
                        {isSignup && isTherapist && (
                            <motion.div
                                key="therapist-fields"
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                className="space-y-5"
                            >
                                <div className="group">
                                    <label className="block text-[10px] font-bold text-foreground/60 uppercase tracking-widest ml-4 mb-2">License Number</label>
                                    <div className="relative">
                                        <BadgeCheck className="absolute left-5 top-1/2 -translate-y-1/2 text-foreground/50 group-focus-within:text-primary transition-colors" size={18} />
                                        <input
                                            type="text"
                                            required
                                            value={licenseNumber}
                                            onChange={(e) => setLicenseNumber(e.target.value)}
                                            placeholder="e.g. PSY-0123456"
                                            className="w-full bg-background border border-border rounded-2xl py-4.5 pl-14 pr-6 focus:outline-none focus:ring-4 focus:ring-primary/20 transition-all text-foreground placeholder:text-foreground/50 shadow-sm"
                                        />
                                    </div>
                                </div>

                                <div className="group">
                                    <label className="block text-[10px] font-bold text-foreground/60 uppercase tracking-widest ml-4 mb-2">Jurisdiction</label>
                                    <input
                                        type="text"
                                        required
                                        value={licenseJurisdiction}
                                        onChange={(e) => setLicenseJurisdiction(e.target.value)}
                                        placeholder="e.g. California, USA"
                                        className="w-full bg-background border border-border rounded-2xl py-4.5 px-6 focus:outline-none focus:ring-4 focus:ring-primary/20 transition-all text-foreground placeholder:text-foreground/50 shadow-sm"
                                    />
                                </div>

                                <div className="group">
                                    <label className="block text-[10px] font-bold text-foreground/60 uppercase tracking-widest ml-4 mb-2">Specializations (comma-separated)</label>
                                    <input
                                        type="text"
                                        value={specializations}
                                        onChange={(e) => setSpecializations(e.target.value)}
                                        placeholder="e.g. CBT, trauma, anxiety"
                                        className="w-full bg-background border border-border rounded-2xl py-4.5 px-6 focus:outline-none focus:ring-4 focus:ring-primary/20 transition-all text-foreground placeholder:text-foreground/50 shadow-sm"
                                    />
                                </div>

                                <div className="rounded-2xl border border-secondary/30 bg-secondary/5 px-5 py-4 text-xs text-foreground/70 leading-relaxed">
                                    Applications are reviewed by our admin team. You'll receive portal access once your license is verified.
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    <motion.div
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        className="pt-4"
                    >
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
                                        {isSignup
                                            ? (isTherapist ? 'Apply For Access' : 'Create Space')
                                            : 'Step Inside'}
                                    </span>
                                    <ArrowRight size={20} className="group-hover:translate-x-1 transition-transform" />
                                </>
                            )}
                        </button>
                    </motion.div>
                </form>

                {!isTherapist && (
                    <>
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
                    </>
                )}

                <div className="mt-12 text-center relative z-10">
                    <p className="text-muted-foreground text-xs font-medium">
                        {isSignup ? "Already Connected?" : "New Presence?"}{' '}
                        <button
                            type="button"
                            onClick={() => setMode(isSignup ? AuthMode.LOGIN : AuthMode.SIGNUP)}
                            className="text-primary font-black hover:text-primary/80 transition-colors uppercase tracking-widest ml-1"
                        >
                            {isSignup ? 'Sign In' : (isTherapist ? 'Apply' : 'Join ELLA')}
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
