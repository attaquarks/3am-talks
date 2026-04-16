import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Navigation, MobileNavigation } from "@/components/Navigation";
import BackgroundDecor from "@/components/auth/BackgroundDecor";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";
import { therapistFetchJson } from "@/lib/therapistFetch";
import { ShieldAlert, Clock, CheckCircle2, XCircle, FileText, LogOut } from "lucide-react";

interface VerificationInfo {
    status?: "pending" | "approved" | "rejected";
    submitted_at?: string;
    reviewed_at?: string;
    reason?: string;
}

export default function TherapistPending() {
    const { user, signOut } = useAuth();
    const navigate = useNavigate();
    const { toast } = useToast();
    const [info, setInfo] = useState<VerificationInfo | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const run = async () => {
            try {
                const data = await therapistFetchJson<{ verification?: VerificationInfo }>("/api/therapist/me");
                setInfo(data?.verification ?? { status: "pending" });
            } catch (err: any) {
                toast({ title: "Couldn't load status", description: err.message, variant: "destructive" });
            } finally {
                setLoading(false);
            }
        };
        run();
    }, [toast]);

    useEffect(() => {
        if (user?.account_status === "active" && user?.role === "therapist") {
            navigate("/therapist-portal");
        }
    }, [user, navigate]);

    const status = info?.status ?? "pending";

    const statusConfig = {
        pending: {
            icon: Clock,
            label: "Under Review",
            color: "text-amber-600 bg-amber-100 dark:bg-amber-950/40",
            message: "Our admin team is reviewing your credentials. This usually takes 1-3 business days.",
        },
        approved: {
            icon: CheckCircle2,
            label: "Approved",
            color: "text-emerald-600 bg-emerald-100 dark:bg-emerald-950/40",
            message: "Welcome aboard! Your portal is ready.",
        },
        rejected: {
            icon: XCircle,
            label: "Needs Attention",
            color: "text-rose-600 bg-rose-100 dark:bg-rose-950/40",
            message: info?.reason ?? "Your application needs revision. You can update your information and re-submit.",
        },
    }[status];

    const StatusIcon = statusConfig.icon;

    return (
        <div className="min-h-screen bg-gradient-to-br from-primary/5 via-background to-secondary/10 relative">
            <BackgroundDecor />
            <Navigation />

            <main className="relative z-10 container mx-auto px-4 sm:px-6 lg:px-8 py-16 max-w-3xl">
                <Card className="rounded-3xl border-border/60 shadow-xl">
                    <CardHeader className="text-center pb-4">
                        <div className="mx-auto mb-6 w-20 h-20 rounded-3xl bg-primary/10 flex items-center justify-center">
                            <ShieldAlert className="h-10 w-10 text-primary" />
                        </div>
                        <CardTitle className="text-3xl font-light tracking-tight">Clinician Verification</CardTitle>
                        <CardDescription className="mt-2 text-base">
                            Thanks for applying to join the Ella clinician network.
                        </CardDescription>
                    </CardHeader>

                    <CardContent className="space-y-6">
                        <div className={`rounded-2xl p-6 ${statusConfig.color}`}>
                            <div className="flex items-start gap-4">
                                <StatusIcon className="h-6 w-6 shrink-0 mt-1" />
                                <div>
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="font-semibold">{statusConfig.label}</span>
                                        <Badge variant="outline" className="text-[10px] uppercase">
                                            {status}
                                        </Badge>
                                    </div>
                                    <p className="text-sm opacity-80 leading-relaxed">{statusConfig.message}</p>
                                </div>
                            </div>
                        </div>

                        <div className="rounded-2xl border border-border p-6 bg-muted/30">
                            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                                <FileText className="h-4 w-4" /> What happens next
                            </h3>
                            <ul className="space-y-2 text-sm text-muted-foreground leading-relaxed">
                                <li className="flex gap-2"><span className="text-primary">•</span> An administrator verifies your license details and credentials.</li>
                                <li className="flex gap-2"><span className="text-primary">•</span> You'll receive an email once the review is complete.</li>
                                <li className="flex gap-2"><span className="text-primary">•</span> Once approved, you'll land on your caseload dashboard automatically.</li>
                                <li className="flex gap-2"><span className="text-primary">•</span> In the meantime, you can update your clinical profile below.</li>
                            </ul>
                        </div>

                        <div className="flex flex-wrap gap-3 justify-center pt-2">
                            <Button variant="outline" onClick={() => navigate("/therapist-portal/profile")}>
                                Edit Clinical Profile
                            </Button>
                            <Button variant="ghost" onClick={async () => { await signOut(); navigate("/auth"); }}>
                                <LogOut className="h-4 w-4 mr-2" /> Sign Out
                            </Button>
                        </div>

                        {loading && (
                            <p className="text-center text-xs text-muted-foreground">Loading status...</p>
                        )}
                    </CardContent>
                </Card>
            </main>

            <MobileNavigation />
        </div>
    );
}
