import { useCallback, useEffect, useState } from "react";
import { Navigation, MobileNavigation } from "@/components/Navigation";
import BackgroundDecor from "@/components/auth/BackgroundDecor";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { therapistFetchJson } from "@/lib/therapistFetch";
import { ConsentPrimer } from "@/components/shared/ConsentPrimer";
import { PatientTherapistLink, ConsentScope } from "@/types/auth";
import {
    HeartHandshake, Eye, ShieldCheck, Sparkles, Mail, UserPlus,
    Loader2, CheckCircle2, XCircle, FileText, History,
} from "lucide-react";

export default function MyTherapists() {
    const { toast } = useToast();

    const [links, setLinks] = useState<PatientTherapistLink[]>([]);
    const [pending, setPending] = useState<PatientTherapistLink[]>([]);
    const [loading, setLoading] = useState(true);

    const [showInvite, setShowInvite] = useState(false);
    const [inviteEmail, setInviteEmail] = useState("");
    const [inviting, setInviting] = useState(false);

    const [consentTarget, setConsentTarget] = useState<PatientTherapistLink | null>(null);
    const [showRevoke, setShowRevoke] = useState<PatientTherapistLink | null>(null);
    const [revokeReason, setRevokeReason] = useState("");

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [linksRes, pendRes] = await Promise.all([
                therapistFetchJson<{ links: PatientTherapistLink[] }>("/api/patient/therapists"),
                therapistFetchJson<{ links: PatientTherapistLink[] }>("/api/links/pending"),
            ]);
            setLinks(linksRes.links || []);
            setPending(pendRes.links || []);
        } catch (err: any) {
            toast({ title: "Couldn't load therapists", description: err.message, variant: "destructive" });
        } finally {
            setLoading(false);
        }
    }, [toast]);

    useEffect(() => { load(); }, [load]);

    const inviteTherapist = async () => {
        setInviting(true);
        try {
            await therapistFetchJson("/api/invite-therapist", {
                method: "POST",
                body: JSON.stringify({ email: inviteEmail }),
            });
            toast({ title: "Request sent", description: "Your therapist will be notified." });
            setInviteEmail("");
            setShowInvite(false);
            await load();
        } catch (err: any) {
            toast({ title: "Invite failed", description: err.message, variant: "destructive" });
        } finally {
            setInviting(false);
        }
    };

    const confirmConsent = async (scope: ConsentScope) => {
        if (!consentTarget) return;
        try {
            await therapistFetchJson(`/api/links/${consentTarget.link_id}/confirm-consent`, {
                method: "POST",
                body: JSON.stringify({ consent_scope: scope }),
            });
            toast({ title: "Link activated", description: "You can now message your therapist." });
            setConsentTarget(null);
            await load();
        } catch (err: any) {
            toast({ title: "Couldn't confirm", description: err.message, variant: "destructive" });
        }
    };

    const acceptPendingLink = async (link: PatientTherapistLink) => {
        try {
            await therapistFetchJson(`/api/links/${link.link_id}/accept`, { method: "POST" });
            setConsentTarget({ ...link, status: "pending_patient" });
            await load();
        } catch (err: any) {
            toast({ title: "Action failed", description: err.message, variant: "destructive" });
        }
    };

    const declineLink = async (linkId: string) => {
        try {
            await therapistFetchJson(`/api/links/${linkId}/decline`, { method: "POST" });
            await load();
        } catch (err: any) {
            toast({ title: "Action failed", description: err.message, variant: "destructive" });
        }
    };

    const revoke = async () => {
        if (!showRevoke) return;
        try {
            await therapistFetchJson(`/api/links/${showRevoke.link_id}/revoke`, {
                method: "POST",
                body: JSON.stringify({ reason: revokeReason }),
            });
            toast({ title: "Access revoked", description: "Your therapist no longer has access to your data." });
            setShowRevoke(null);
            setRevokeReason("");
            await load();
        } catch (err: any) {
            toast({ title: "Revoke failed", description: err.message, variant: "destructive" });
        }
    };

    const activeLinks = links.filter((l) => l.status === "active");

    return (
        <div className="min-h-screen bg-gradient-to-br from-primary/10 via-background to-secondary/10 relative">
            <BackgroundDecor />
            <Navigation />

            <main className="relative z-10 container mx-auto px-4 sm:px-6 lg:px-8 py-10 pb-24 max-w-5xl space-y-6">
                <div className="flex items-center gap-3">
                    <HeartHandshake className="h-8 w-8 text-primary" />
                    <div>
                        <h1 className="text-3xl font-light tracking-tight">My Therapists</h1>
                        <p className="text-sm text-muted-foreground">Real human support, on your terms.</p>
                    </div>
                </div>

                {loading ? (
                    <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>
                ) : (
                    <>
                        {/* Pending requests */}
                        {pending.length > 0 && (
                            <Card className="rounded-3xl border-primary/30">
                                <CardHeader>
                                    <CardTitle className="text-base">Pending requests</CardTitle>
                                    <CardDescription>Review each request carefully. You must confirm data sharing before anything is visible.</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-3">
                                    {pending.map((link) => (
                                        <div key={link.link_id} className="flex items-center justify-between gap-4 p-4 rounded-2xl border border-border bg-muted/30">
                                            <div>
                                                <div className="flex items-center gap-2 mb-1">
                                                    <p className="font-medium">{link.counterparty?.display_name || link.counterparty?.name || link.counterparty?.email}</p>
                                                    <Badge variant="outline">{link.status.replace("_", " ")}</Badge>
                                                </div>
                                                {link.counterparty?.title && <p className="text-xs text-muted-foreground">{link.counterparty.title}</p>}
                                                <p className="text-xs text-muted-foreground mt-1">
                                                    {link.status === "pending_patient"
                                                        ? "Therapist accepted. Confirm what you want to share to activate."
                                                        : "Waiting for therapist to accept your request."}
                                                </p>
                                            </div>
                                            <div className="flex gap-2">
                                                {link.status === "pending_patient" ? (
                                                    <Button size="sm" onClick={() => setConsentTarget(link)}>
                                                        <ShieldCheck className="h-4 w-4 mr-1" /> Review & consent
                                                    </Button>
                                                ) : link.initiated_by && link.initiated_by !== link.patient_id ? (
                                                    <>
                                                        <Button variant="outline" size="sm" onClick={() => declineLink(link.link_id)}>
                                                            <XCircle className="h-4 w-4 mr-1" /> Decline
                                                        </Button>
                                                        <Button size="sm" onClick={() => acceptPendingLink(link)}>
                                                            <CheckCircle2 className="h-4 w-4 mr-1" /> Accept
                                                        </Button>
                                                    </>
                                                ) : (
                                                    <Badge variant="outline">Awaiting response</Badge>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </CardContent>
                            </Card>
                        )}

                        {/* Active links or empty state */}
                        {activeLinks.length === 0 && pending.length === 0 ? (
                            <Card className="rounded-[2.5rem] overflow-hidden border-primary/20 shadow-xl">
                                <CardContent className="p-10 md:p-14 relative">
                                    <div className="absolute top-0 right-0 w-64 h-64 bg-primary/10 rounded-full blur-3xl" />
                                    <div className="relative z-10 max-w-2xl mx-auto text-center">
                                        <div className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-primary/15 text-primary mb-6">
                                            <Sparkles className="h-10 w-10" />
                                        </div>
                                        <h2 className="text-3xl font-light tracking-tight mb-3">A human in your corner</h2>
                                        <p className="text-muted-foreground leading-relaxed max-w-md mx-auto mb-8">
                                            Ella is here every night, but sometimes you want a trained professional to walk alongside you. Link a therapist to share the data you choose and get real, grounded support.
                                        </p>

                                        <div className="grid md:grid-cols-3 gap-4 text-left mb-10">
                                            <BenefitCard
                                                icon={HeartHandshake}
                                                title="Someone who knows you"
                                                body="Your therapist sees the context you want to share, so sessions can start deeper."
                                            />
                                            <BenefitCard
                                                icon={Eye}
                                                title="You control what's shared"
                                                body="Pick exactly which categories (mood, chats, journals) are visible. Revoke anytime."
                                            />
                                            <BenefitCard
                                                icon={ShieldCheck}
                                                title="Private notes stay private"
                                                body="Your therapist's notes are never shown to you. Your data is never shared without consent."
                                            />
                                        </div>

                                        <Button size="lg" className="rounded-xl" onClick={() => setShowInvite(true)}>
                                            <UserPlus className="h-5 w-5 mr-2" /> Invite your therapist
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        ) : null}

                        {activeLinks.length > 0 && (
                            <>
                                <div className="flex items-center justify-between">
                                    <h2 className="text-lg font-semibold">Linked therapists</h2>
                                    <Button variant="outline" onClick={() => setShowInvite(true)}>
                                        <UserPlus className="h-4 w-4 mr-2" /> Invite another
                                    </Button>
                                </div>
                                <div className="grid md:grid-cols-2 gap-4">
                                    {activeLinks.map((link) => (
                                        <Card key={link.link_id} className="rounded-3xl">
                                            <CardContent className="p-6 space-y-4">
                                                <div className="flex items-start gap-4">
                                                    <div className="h-14 w-14 rounded-2xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
                                                        <HeartHandshake className="h-6 w-6" />
                                                    </div>
                                                    <div className="flex-1">
                                                        <p className="font-semibold">{link.counterparty?.display_name || link.counterparty?.name || link.counterparty?.email}</p>
                                                        {link.counterparty?.title && <p className="text-xs text-muted-foreground">{link.counterparty.title}</p>}
                                                        {link.counterparty?.specializations && link.counterparty.specializations.length > 0 && (
                                                            <div className="flex flex-wrap gap-1 mt-2">
                                                                {link.counterparty.specializations.slice(0, 4).map((s, i) => <Badge key={i} variant="outline" className="text-[10px]">{s}</Badge>)}
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>

                                                <div className="rounded-xl bg-muted/40 p-3 text-xs">
                                                    <p className="font-medium mb-1 flex items-center gap-1"><Eye className="h-3 w-3" /> Currently sharing</p>
                                                    <div className="flex flex-wrap gap-1">
                                                        {Object.entries(link.consent_scope ?? {})
                                                            .filter(([, v]) => v)
                                                            .map(([k]) => <Badge key={k} variant="secondary" className="text-[10px]">{k}</Badge>)}
                                                    </div>
                                                </div>

                                                <div className="flex justify-between gap-2">
                                                    <Button variant="ghost" size="sm" onClick={() => setConsentTarget(link)}>
                                                        <ShieldCheck className="h-4 w-4 mr-1" /> Edit sharing
                                                    </Button>
                                                    <Button variant="destructive" size="sm" onClick={() => setShowRevoke(link)}>
                                                        Revoke access
                                                    </Button>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            </>
                        )}

                        <Card className="rounded-3xl border-muted">
                            <CardContent className="p-5 flex items-center justify-between gap-4 flex-wrap">
                                <div className="flex items-center gap-3">
                                    <History className="h-5 w-5 text-muted-foreground" />
                                    <div>
                                        <p className="text-sm font-medium">Transparency log</p>
                                        <p className="text-xs text-muted-foreground">See every time a linked therapist accessed your data.</p>
                                    </div>
                                </div>
                                <Button variant="outline" size="sm" asChild>
                                    <a href="/my-therapists/access-log"><FileText className="h-4 w-4 mr-1" /> View log</a>
                                </Button>
                            </CardContent>
                        </Card>
                    </>
                )}
            </main>

            <MobileNavigation />

            {/* Invite therapist dialog */}
            <Dialog open={showInvite} onOpenChange={setShowInvite}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Invite your therapist</DialogTitle>
                        <DialogDescription>
                            If they already have an Ella clinician account, we'll send them a link request. If not, we'll email them an invite to join.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-2 py-2">
                        <Label>Therapist's email</Label>
                        <div className="relative">
                            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                            <Input
                                className="pl-10"
                                type="email"
                                value={inviteEmail}
                                onChange={(e) => setInviteEmail(e.target.value)}
                                placeholder="therapist@example.com"
                            />
                        </div>
                    </div>
                    <div className="rounded-xl bg-muted/40 px-4 py-3 text-xs text-muted-foreground leading-relaxed">
                        Nothing is shared yet. After they accept, you'll review exactly what to share before activation.
                    </div>
                    <DialogFooter>
                        <Button variant="ghost" onClick={() => setShowInvite(false)}>Cancel</Button>
                        <Button onClick={inviteTherapist} disabled={!inviteEmail || inviting}>
                            {inviting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            Send request
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Revoke dialog */}
            <Dialog open={!!showRevoke} onOpenChange={(v) => !v && setShowRevoke(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Revoke therapist access?</DialogTitle>
                        <DialogDescription>
                            They will immediately lose access to all your data. You can re-link later if you change your mind.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-2 py-2">
                        <Label>Reason (optional)</Label>
                        <Input
                            value={revokeReason}
                            onChange={(e) => setRevokeReason(e.target.value)}
                            placeholder="Short note for your records"
                        />
                    </div>
                    <DialogFooter>
                        <Button variant="ghost" onClick={() => setShowRevoke(null)}>Cancel</Button>
                        <Button variant="destructive" onClick={revoke}>Revoke access</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {consentTarget && (
                <ConsentPrimer
                    open={!!consentTarget}
                    onClose={() => setConsentTarget(null)}
                    onConfirm={confirmConsent}
                    therapistName={consentTarget.counterparty?.display_name || consentTarget.counterparty?.name}
                    initialScope={consentTarget.consent_scope}
                    mode={consentTarget.status === "active" ? "review" : "grant"}
                />
            )}
        </div>
    );
}

function BenefitCard({ icon: Icon, title, body }: { icon: typeof HeartHandshake; title: string; body: string }) {
    return (
        <div className="rounded-2xl border border-border/60 bg-card p-5">
            <div className="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-3">
                <Icon className="h-5 w-5" />
            </div>
            <p className="font-medium text-sm mb-1">{title}</p>
            <p className="text-xs text-muted-foreground leading-relaxed">{body}</p>
        </div>
    );
}
