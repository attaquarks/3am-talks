import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Navigation, MobileNavigation } from "@/components/Navigation";
import BackgroundDecor from "@/components/auth/BackgroundDecor";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { therapistFetchJson } from "@/lib/therapistFetch";
import { CaseloadPatient, PatientTherapistLink, SecureMessage, CrisisEvent } from "@/types/auth";
import {
    Users, Inbox, AlertTriangle, TrendingUp, UserPlus, Briefcase,
    Search, Loader2, CheckCircle2, XCircle, Clock, Activity, Mail, MessageSquare, ArrowRight,
} from "lucide-react";

interface MessageThread {
    link_id: string;
    counterparty?: { name?: string; email?: string; display_name?: string };
    last_message?: SecureMessage | null;
    unread_count?: number;
}

type Tab = "overview" | "clients" | "requests" | "messages" | "crisis" | "settings";

const pathToTab = (pathname: string): Tab =>
    pathname.endsWith("/clients") ? "clients" : "overview";

export default function TherapistDashboard() {
    const navigate = useNavigate();
    const location = useLocation();
    const { toast } = useToast();

    const [tab, setTab] = useState<Tab>(() => pathToTab(location.pathname));

    useEffect(() => {
        const urlTab = pathToTab(location.pathname);
        setTab((prev) => {
            // Only overwrite from URL when URL points at a routed tab. If the user
            // is on an inner-only tab (requests/crisis/messages) keep their selection.
            if (urlTab === "clients") return "clients";
            if (prev === "overview" || prev === "clients") return urlTab;
            return prev;
        });
    }, [location.pathname]);

    const handleTabChange = (v: string) => {
        const next = v as Tab;
        setTab(next);
        if (next === "clients" && !location.pathname.endsWith("/clients")) {
            navigate("/therapist-portal/clients", { replace: true });
        } else if (next === "overview" && location.pathname !== "/therapist-portal") {
            navigate("/therapist-portal", { replace: true });
        }
    };
    const [loading, setLoading] = useState(true);
    const [caseload, setCaseload] = useState<CaseloadPatient[]>([]);
    const [pendingLinks, setPendingLinks] = useState<PatientTherapistLink[]>([]);
    const [crisisEvents, setCrisisEvents] = useState<CrisisEvent[]>([]);
    const [threads, setThreads] = useState<MessageThread[]>([]);
    const [search, setSearch] = useState("");
    const [inviteEmail, setInviteEmail] = useState("");
    const [showInviteDialog, setShowInviteDialog] = useState(false);
    const [inviting, setInviting] = useState(false);

    const loadAll = useCallback(async () => {
        setLoading(true);
        try {
            const [caseRes, linksRes, crisisRes, msgRes] = await Promise.all([
                therapistFetchJson<{ patients: CaseloadPatient[] }>("/api/therapist/patients"),
                therapistFetchJson<{ links: PatientTherapistLink[] }>("/api/links/pending"),
                therapistFetchJson<{ events: CrisisEvent[] }>("/api/therapist/crisis"),
                therapistFetchJson<{ threads: MessageThread[] }>("/api/therapist/messages"),
            ]);
            setCaseload(caseRes.patients || []);
            setPendingLinks(linksRes.links || []);
            setCrisisEvents(crisisRes.events || []);
            setThreads(msgRes.threads || []);
        } catch (err: any) {
            toast({ title: "Couldn't load data", description: err.message, variant: "destructive" });
        } finally {
            setLoading(false);
        }
    }, [toast]);

    useEffect(() => {
        loadAll();
    }, [loadAll]);

    const acceptLink = async (linkId: string) => {
        try {
            await therapistFetchJson(`/api/links/${linkId}/accept`, { method: "POST" });
            toast({ title: "Request accepted", description: "Patient must confirm consent to activate." });
            await loadAll();
        } catch (err: any) {
            toast({ title: "Action failed", description: err.message, variant: "destructive" });
        }
    };

    const declineLink = async (linkId: string) => {
        try {
            await therapistFetchJson(`/api/links/${linkId}/decline`, { method: "POST" });
            toast({ title: "Request declined" });
            await loadAll();
        } catch (err: any) {
            toast({ title: "Action failed", description: err.message, variant: "destructive" });
        }
    };

    const invitePatient = async () => {
        setInviting(true);
        try {
            await therapistFetchJson("/api/therapist/invite-patient", {
                method: "POST",
                body: JSON.stringify({ email: inviteEmail }),
            });
            toast({ title: "Invitation sent", description: `Invite delivered to ${inviteEmail}.` });
            setInviteEmail("");
            setShowInviteDialog(false);
            await loadAll();
        } catch (err: any) {
            toast({ title: "Invite failed", description: err.message, variant: "destructive" });
        } finally {
            setInviting(false);
        }
    };

    const filteredCaseload = useMemo(() => {
        const q = search.trim().toLowerCase();
        if (!q) return caseload;
        return caseload.filter(
            (p) =>
                (p.name ?? "").toLowerCase().includes(q) ||
                (p.email ?? "").toLowerCase().includes(q) ||
                (p.risk_level ?? "").toLowerCase().includes(q)
        );
    }, [caseload, search]);

    const stats = useMemo(() => {
        const active = caseload.length;
        const highRisk = caseload.filter((p) => ["high", "critical"].includes((p.risk_level ?? "").toLowerCase())).length;
        const crisis = crisisEvents.filter((c) => !c.resolved_at).length;
        const totalSessions = caseload.reduce((sum, p) => sum + (p.total_sessions ?? 0), 0);
        return { active, highRisk, crisis, totalSessions };
    }, [caseload, crisisEvents]);

    const riskBadge = (risk?: string) => {
        const r = (risk ?? "").toLowerCase();
        const colors: Record<string, string> = {
            critical: "bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300",
            high: "bg-orange-100 text-orange-700 dark:bg-orange-950/40 dark:text-orange-300",
            medium: "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
            low: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300",
        };
        return <Badge variant="outline" className={colors[r] ?? ""}>{r || "unknown"}</Badge>;
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-primary/5 via-background to-secondary/10 relative">
            <BackgroundDecor />
            <Navigation />

            <main className="relative z-10 container mx-auto px-4 sm:px-6 lg:px-8 py-10 pb-24 space-y-6">
                <div className="flex items-center justify-between flex-wrap gap-3">
                    <div>
                        <h1 className="text-3xl font-light tracking-tight flex items-center gap-3">
                            <Briefcase className="h-8 w-8 text-primary" /> Clinician Portal
                        </h1>
                        <p className="text-sm text-muted-foreground mt-1">Your caseload at a glance.</p>
                    </div>
                    <Button onClick={() => setShowInviteDialog(true)} className="rounded-xl">
                        <UserPlus className="h-4 w-4 mr-2" /> Invite Patient
                    </Button>
                </div>

                {/* Stat cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard icon={Users} label="Active clients" value={stats.active} color="text-primary" />
                    <StatCard icon={AlertTriangle} label="High risk" value={stats.highRisk} color="text-orange-500" />
                    <StatCard icon={Activity} label="Open crisis events" value={stats.crisis} color="text-rose-500" />
                    <StatCard icon={TrendingUp} label="Total sessions" value={stats.totalSessions} color="text-emerald-500" />
                </div>

                <Tabs value={tab} onValueChange={handleTabChange}>
                    <TabsList className="grid w-full max-w-3xl grid-cols-5">
                        <TabsTrigger value="overview">Overview</TabsTrigger>
                        <TabsTrigger value="clients">Clients</TabsTrigger>
                        <TabsTrigger value="requests">
                            Requests {pendingLinks.length > 0 && <Badge className="ml-2 h-5 px-1.5 text-[10px]">{pendingLinks.length}</Badge>}
                        </TabsTrigger>
                        <TabsTrigger value="crisis">
                            Crisis {stats.crisis > 0 && <Badge variant="destructive" className="ml-2 h-5 px-1.5 text-[10px]">{stats.crisis}</Badge>}
                        </TabsTrigger>
                        <TabsTrigger value="messages">Messages</TabsTrigger>
                    </TabsList>

                    <TabsContent value="overview" className="space-y-6 mt-6">
                        <Card className="rounded-3xl">
                            <CardHeader>
                                <CardTitle>Recent activity</CardTitle>
                                <CardDescription>A snapshot across your caseload.</CardDescription>
                            </CardHeader>
                            <CardContent>
                                {loading ? (
                                    <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin" /></div>
                                ) : caseload.length === 0 ? (
                                    <EmptyState
                                        icon={Users}
                                        title="No linked patients yet"
                                        description="Once a patient accepts a link request, they'll appear here with their session activity and mood trends."
                                        action={<Button onClick={() => setShowInviteDialog(true)}><UserPlus className="h-4 w-4 mr-2" /> Invite your first patient</Button>}
                                    />
                                ) : (
                                    <div className="space-y-3">
                                        {caseload.slice(0, 5).map((p) => (
                                            <button
                                                key={p.link_id}
                                                onClick={() => navigate(`/therapist-portal/patients/${p.patient_id}`)}
                                                className="w-full flex items-center justify-between gap-4 p-4 rounded-2xl border border-border hover:bg-muted/40 transition-colors text-left"
                                            >
                                                <div>
                                                    <p className="font-medium">{p.name || p.email || p.patient_id}</p>
                                                    <p className="text-xs text-muted-foreground">
                                                        Last session: {p.last_session_at ? new Date(p.last_session_at).toLocaleDateString() : "—"} · {p.total_sessions} total
                                                    </p>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    {p.unresolved_crisis && <Badge variant="destructive">Crisis</Badge>}
                                                    {riskBadge(p.risk_level)}
                                                </div>
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>

                    <TabsContent value="clients" className="space-y-4 mt-6">
                        <div className="flex items-center gap-2 max-w-md">
                            <Search className="h-4 w-4 text-muted-foreground" />
                            <Input
                                placeholder="Search by name, email, risk..."
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                            />
                        </div>

                        <Card className="rounded-3xl overflow-hidden">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Patient</TableHead>
                                        <TableHead>Linked since</TableHead>
                                        <TableHead>Last session</TableHead>
                                        <TableHead>Sessions</TableHead>
                                        <TableHead>Risk</TableHead>
                                        <TableHead></TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {filteredCaseload.length === 0 && (
                                        <TableRow><TableCell colSpan={6} className="text-center py-12 text-muted-foreground">No matches.</TableCell></TableRow>
                                    )}
                                    {filteredCaseload.map((p) => (
                                        <TableRow key={p.link_id}>
                                            <TableCell>
                                                <div>
                                                    <p className="font-medium">{p.name || p.email || p.patient_id}</p>
                                                    {p.email && <p className="text-xs text-muted-foreground">{p.email}</p>}
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-sm">{p.linked_since ? new Date(p.linked_since).toLocaleDateString() : "—"}</TableCell>
                                            <TableCell className="text-sm">{p.last_session_at ? new Date(p.last_session_at).toLocaleDateString() : "—"}</TableCell>
                                            <TableCell className="text-sm">{p.total_sessions}</TableCell>
                                            <TableCell>{riskBadge(p.risk_level)}</TableCell>
                                            <TableCell className="text-right">
                                                <Button variant="outline" size="sm" onClick={() => navigate(`/therapist-portal/patients/${p.patient_id}`)}>
                                                    View
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </Card>
                    </TabsContent>

                    <TabsContent value="requests" className="space-y-4 mt-6">
                        {pendingLinks.length === 0 ? (
                            <EmptyState icon={Inbox} title="No pending requests" description="Link requests from patients or acceptances awaiting consent show here." />
                        ) : (
                            pendingLinks.map((link) => (
                                <Card key={link.link_id} className="rounded-3xl">
                                    <CardContent className="flex items-center justify-between gap-4 p-6">
                                        <div>
                                            <div className="flex items-center gap-2 mb-1">
                                                <p className="font-medium">{link.counterparty?.name || link.counterparty?.email || link.patient_id}</p>
                                                <Badge variant={link.status === "pending_therapist" ? "default" : "secondary"}>
                                                    {link.status.replace("_", " ")}
                                                </Badge>
                                            </div>
                                            <p className="text-xs text-muted-foreground">
                                                {link.status === "pending_therapist"
                                                    ? "Patient is requesting to link with you."
                                                    : "Waiting for patient to confirm consent."}
                                            </p>
                                        </div>
                                        <div className="flex gap-2">
                                            {link.status === "pending_therapist" && (
                                                <>
                                                    <Button variant="outline" size="sm" onClick={() => declineLink(link.link_id)}>
                                                        <XCircle className="h-4 w-4 mr-1" /> Decline
                                                    </Button>
                                                    <Button size="sm" onClick={() => acceptLink(link.link_id)}>
                                                        <CheckCircle2 className="h-4 w-4 mr-1" /> Accept
                                                    </Button>
                                                </>
                                            )}
                                            {link.status === "pending_patient" && (
                                                <Badge variant="outline"><Clock className="h-3 w-3 mr-1" /> Awaiting patient</Badge>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            ))
                        )}
                    </TabsContent>

                    <TabsContent value="crisis" className="space-y-4 mt-6">
                        {crisisEvents.length === 0 ? (
                            <EmptyState icon={AlertTriangle} title="No crisis events" description="Any automatic or manual escalations will appear here." />
                        ) : (
                            crisisEvents.map((event) => {
                                const patientName = caseload.find((p) => p.patient_id === event.patient_id)?.name
                                    ?? caseload.find((p) => p.patient_id === event.patient_id)?.email
                                    ?? event.patient_id;
                                const openPatient = () =>
                                    navigate(`/therapist-portal/patients/${event.patient_id}?tab=crisis&event=${event.event_id}`);
                                return (
                                    <Card
                                        key={event.event_id}
                                        role="button"
                                        tabIndex={0}
                                        onClick={openPatient}
                                        onKeyDown={(e) => {
                                            if (e.key === "Enter" || e.key === " ") {
                                                e.preventDefault();
                                                openPatient();
                                            }
                                        }}
                                        className={`rounded-3xl cursor-pointer transition-all hover:shadow-lg hover:border-rose-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400 ${!event.resolved_at ? "border-rose-300 shadow-rose-100" : ""}`}
                                    >
                                        <CardContent className="p-6 space-y-3">
                                            <div className="flex items-center justify-between gap-2 flex-wrap">
                                                <div className="flex items-center gap-2 flex-wrap">
                                                    <Badge variant={event.severity === "critical" || event.severity === "high" ? "destructive" : "outline"}>
                                                        {event.severity}
                                                    </Badge>
                                                    {typeof event.severity_score === "number" && (
                                                        <Badge variant="outline" className="text-[10px]">score {event.severity_score.toFixed(2)}</Badge>
                                                    )}
                                                    {event.intervention_type && event.intervention_type !== "modal_shown" && (
                                                        <Badge variant="secondary" className="text-[10px]">{event.intervention_type.replace(/_/g, " ")}</Badge>
                                                    )}
                                                    <span className="text-xs text-muted-foreground">
                                                        {event.created_at && new Date(event.created_at).toLocaleString()}
                                                    </span>
                                                </div>
                                                {event.resolved_at ? (
                                                    <Badge variant="secondary">Resolved</Badge>
                                                ) : (
                                                    <span className="text-xs text-rose-600 font-medium inline-flex items-center gap-1">
                                                        Open patient file <ArrowRight className="h-3.5 w-3.5" />
                                                    </span>
                                                )}
                                            </div>
                                            <div className="text-sm">
                                                <p className="font-medium">{patientName}</p>
                                                <p className="text-xs text-muted-foreground">Triggered by: {event.triggered_by}</p>
                                            </div>
                                            {event.trigger_text && (
                                                <div className="rounded-xl border border-border bg-muted/30 p-3">
                                                    <p className="text-[11px] uppercase tracking-wide text-muted-foreground mb-1">What triggered this</p>
                                                    <p className="text-sm whitespace-pre-wrap line-clamp-4">{event.trigger_text}</p>
                                                </div>
                                            )}
                                            {event.keyword_matches && event.keyword_matches.length > 0 && (
                                                <div className="flex flex-wrap gap-1">
                                                    {event.keyword_matches.slice(0, 8).map((kw, i) => (
                                                        <Badge key={i} variant="outline" className="text-[10px]">{kw}</Badge>
                                                    ))}
                                                </div>
                                            )}
                                        </CardContent>
                                    </Card>
                                );
                            })
                        )}
                    </TabsContent>

                    <TabsContent value="messages" className="space-y-4 mt-6">
                        {threads.length === 0 ? (
                            <EmptyState
                                icon={MessageSquare}
                                title="No conversations yet"
                                description="Threads with your patients will appear here once you're linked."
                                action={<Button variant="outline" onClick={() => navigate("/therapist-portal/messages")}><Inbox className="h-4 w-4 mr-2" /> Open inbox</Button>}
                            />
                        ) : (
                            <>
                                <Button variant="outline" onClick={() => navigate("/therapist-portal/messages")}><Inbox className="h-4 w-4 mr-2" /> Open full inbox</Button>
                                {threads.slice(0, 10).map((t) => {
                                    const name = t.counterparty?.display_name || t.counterparty?.name || t.counterparty?.email || "Patient";
                                    const last = t.last_message;
                                    return (
                                        <Card key={t.link_id} className="rounded-2xl cursor-pointer hover:bg-muted/40" onClick={() => navigate("/therapist-portal/messages")}>
                                            <CardContent className="p-4">
                                                <div className="flex items-center justify-between mb-2 gap-2">
                                                    <p className="font-medium text-sm">{name}</p>
                                                    <div className="flex items-center gap-2">
                                                        {(t.unread_count ?? 0) > 0 && <Badge className="h-5 px-1.5 text-[10px]">{t.unread_count}</Badge>}
                                                        {last?.urgency && last.urgency !== "normal" && (
                                                            <Badge variant={last.urgency === "urgent" ? "destructive" : "default"} className="text-[10px]">{last.urgency}</Badge>
                                                        )}
                                                        <span className="text-xs text-muted-foreground">
                                                            {last?.created_at && new Date(last.created_at).toLocaleString()}
                                                        </span>
                                                    </div>
                                                </div>
                                                <p className="text-sm line-clamp-2 text-muted-foreground">{last?.body ?? "No messages yet."}</p>
                                            </CardContent>
                                        </Card>
                                    );
                                })}
                            </>
                        )}
                    </TabsContent>
                </Tabs>
            </main>

            <MobileNavigation />

            <Dialog open={showInviteDialog} onOpenChange={setShowInviteDialog}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>Invite a patient</DialogTitle>
                        <DialogDescription>
                            We'll send them an invite to accept linking with you. They must explicitly consent to data sharing before you see their data.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-2 py-2">
                        <Label>Patient email</Label>
                        <div className="relative">
                            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                            <Input
                                className="pl-10"
                                type="email"
                                value={inviteEmail}
                                onChange={(e) => setInviteEmail(e.target.value)}
                                placeholder="patient@example.com"
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="ghost" onClick={() => setShowInviteDialog(false)}>Cancel</Button>
                        <Button onClick={invitePatient} disabled={!inviteEmail || inviting}>
                            {inviting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                            Send invite
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}

function StatCard({ icon: Icon, label, value, color }: { icon: typeof Users; label: string; value: number | string; color: string }) {
    return (
        <Card className="rounded-2xl">
            <CardContent className="p-5 flex items-center gap-4">
                <div className={`h-11 w-11 rounded-2xl bg-muted flex items-center justify-center ${color}`}>
                    <Icon className="h-5 w-5" />
                </div>
                <div>
                    <p className="text-2xl font-bold">{value}</p>
                    <p className="text-xs text-muted-foreground">{label}</p>
                </div>
            </CardContent>
        </Card>
    );
}

function EmptyState({ icon: Icon, title, description, action }: { icon: typeof Users; title: string; description: string; action?: React.ReactNode }) {
    return (
        <div className="text-center py-12 px-6">
            <div className="mx-auto mb-4 w-16 h-16 rounded-2xl bg-muted flex items-center justify-center">
                <Icon className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="font-semibold mb-2">{title}</h3>
            <p className="text-sm text-muted-foreground max-w-md mx-auto mb-6">{description}</p>
            {action}
        </div>
    );
}
