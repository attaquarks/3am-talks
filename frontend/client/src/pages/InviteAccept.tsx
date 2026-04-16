import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import BackgroundDecor from "@/components/auth/BackgroundDecor";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/hooks/useAuth";
import { therapistFetchJson } from "@/lib/therapistFetch";
import { HeartHandshake, Loader2, Sparkles, Wind } from "lucide-react";

interface InviteInfo {
    invite_type: "patient_invites_therapist" | "therapist_invites_patient";
    inviter_name?: string;
    inviter_email?: string;
    invitee_email?: string;
    status?: string;
    expires_at?: string;
}

export default function InviteAccept() {
    const [params] = useSearchParams();
    const token = params.get("token");
    const navigate = useNavigate();
    const { toast } = useToast();
    const { user } = useAuth();

    const [info, setInfo] = useState<InviteInfo | null>(null);
    const [loading, setLoading] = useState(true);
    const [accepting, setAccepting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!token) { setError("Missing invite token"); setLoading(false); return; }
        const run = async () => {
            try {
                const data = await therapistFetchJson<InviteInfo>(`/api/invite/info?token=${token}`);
                setInfo(data);
            } catch (err: any) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };
        run();
    }, [token]);

    const accept = async () => {
        if (!token) return;
        if (!user) {
            navigate(`/auth?invite=${token}`);
            return;
        }
        setAccepting(true);
        try {
            const data = await therapistFetchJson<{ link_id?: string; redirect?: string }>(`/api/invite/accept`, {
                method: "POST",
                body: JSON.stringify({ token }),
            });
            toast({ title: "Invite accepted", description: "Head to the next step to confirm consent." });
            navigate(data?.redirect ?? (user.role === "therapist" ? "/therapist-portal" : "/my-therapists"));
        } catch (err: any) {
            toast({ title: "Accept failed", description: err.message, variant: "destructive" });
        } finally {
            setAccepting(false);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-primary/10 via-background to-secondary/10 relative flex flex-col items-center">
            <BackgroundDecor />

            <nav className="w-full max-w-7xl px-8 py-8 z-10">
                <Link to="/" className="flex items-center gap-3 group">
                    <div className="relative w-10 h-10 flex items-center justify-center">
                        <Wind className="absolute text-primary/40 group-hover:rotate-12 transition-all" size={28} strokeWidth={1.5} />
                        <Sparkles className="absolute text-accent/60 -top-1 -right-1 animate-pulse" size={14} />
                    </div>
                    <span className="text-xl font-light tracking-[0.2em] uppercase">
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-secondary to-accent">Ella AI</span>
                    </span>
                </Link>
            </nav>

            <main className="flex-1 w-full max-w-xl px-6 flex items-center justify-center z-10">
                <Card className="w-full rounded-[2.5rem] shadow-xl border-primary/20">
                    <CardHeader className="text-center pb-4">
                        <div className="mx-auto mb-6 w-20 h-20 rounded-3xl bg-primary/10 flex items-center justify-center">
                            <HeartHandshake className="h-10 w-10 text-primary" />
                        </div>
                        <CardTitle className="text-3xl font-light tracking-tight">You've been invited</CardTitle>
                        <CardDescription className="text-base pt-2">
                            {loading ? "Loading your invite..." : error ? "Invite not found" : ""}
                        </CardDescription>
                    </CardHeader>

                    <CardContent className="space-y-6 pb-8">
                        {loading ? (
                            <div className="flex justify-center py-10"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>
                        ) : error ? (
                            <div className="text-center space-y-4">
                                <p className="text-sm text-muted-foreground">{error}</p>
                                <Button variant="outline" asChild><Link to="/">Go home</Link></Button>
                            </div>
                        ) : (
                            <>
                                <div className="rounded-2xl border border-border p-5 space-y-2 text-sm">
                                    <p><strong>From:</strong> {info?.inviter_name ?? info?.inviter_email ?? "—"}</p>
                                    <p><strong>Type:</strong> {info?.invite_type === "therapist_invites_patient"
                                        ? "A therapist wants to link with you"
                                        : "A patient wants you to be their therapist"}</p>
                                    {info?.expires_at && <p className="text-xs text-muted-foreground">Expires {new Date(info.expires_at).toLocaleDateString()}</p>}
                                </div>

                                <div className="rounded-2xl bg-primary/5 border border-primary/20 px-5 py-4 text-sm leading-relaxed">
                                    {info?.invite_type === "therapist_invites_patient"
                                        ? "By accepting, a link request is created. You'll then choose exactly which data categories to share. You can revoke access any time."
                                        : "By accepting, you'll be offered a link with this patient. They'll pick what data to share before anything is visible to you."}
                                </div>

                                {user ? (
                                    <Button size="lg" className="w-full rounded-xl" onClick={accept} disabled={accepting}>
                                        {accepting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                                        Accept invite
                                    </Button>
                                ) : (
                                    <div className="space-y-3">
                                        <p className="text-sm text-muted-foreground text-center">Sign in or create an account to accept.</p>
                                        <Button size="lg" className="w-full rounded-xl" asChild>
                                            <Link to={`/auth?invite=${token}`}>Sign in to accept</Link>
                                        </Button>
                                    </div>
                                )}
                            </>
                        )}
                    </CardContent>
                </Card>
            </main>

            <footer className="w-full max-w-7xl px-8 py-10 z-10 text-center">
                <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-muted-foreground opacity-60">
                    Safe · Secure · Compassionate
                </p>
            </footer>
        </div>
    );
}
