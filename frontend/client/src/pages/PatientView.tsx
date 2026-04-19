import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Navigation, MobileNavigation } from "@/components/Navigation";
import BackgroundDecor from "@/components/auth/BackgroundDecor";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { therapistFetch, therapistFetchJson } from "@/lib/therapistFetch";
import {
    SessionSummary, TherapistNote, TreatmentPlan, HomeworkItem, CrisisEvent,
} from "@/types/auth";
import {
    ArrowLeft, FileText, StickyNote, ClipboardList, Activity, AlertTriangle,
    Loader2, Download, Plus, Calendar, Trash2, Brain, Smile, CheckCircle2,
} from "lucide-react";

interface PatientDetail {
    user_id: string;
    name?: string;
    email?: string;
    personality?: Record<string, unknown>;
    stats?: Record<string, unknown>;
    linked_since?: string;
    consent_scope?: Record<string, boolean>;
}

interface ConversationItem {
    conversation_id: string;
    title?: string;
    started_at?: string;
    ended_at?: string;
    message_count?: number;
    has_summary?: boolean;
}

interface MessageItem {
    message_id: string;
    role: string;
    content: string;
    created_at?: string;
}

interface MoodEntry {
    entry_id?: string;
    mood?: string;
    note?: string;
    created_at?: string;
}

interface PrepBrief {
    top_concerns?: string[];
    recent_shifts?: string;
    unresolved_topics?: string[];
    suggested_focus?: string;
    risk_notes?: string;
}

export default function PatientView() {
    const { id: patientId } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const { toast } = useToast();
    const [searchParams] = useSearchParams();
    const initialTab = searchParams.get("tab") || "sessions";
    const focusEventId = searchParams.get("event");
    const focusEventRef = useRef<HTMLDivElement>(null);

    const [loading, setLoading] = useState(true);
    const [patient, setPatient] = useState<PatientDetail | null>(null);
    const [conversations, setConversations] = useState<ConversationItem[]>([]);
    const [mood, setMood] = useState<MoodEntry[]>([]);
    const [notes, setNotes] = useState<TherapistNote[]>([]);
    const [plans, setPlans] = useState<TreatmentPlan[]>([]);
    const [homework, setHomework] = useState<HomeworkItem[]>([]);
    const [crisis, setCrisis] = useState<CrisisEvent[]>([]);
    const [prepBrief, setPrepBrief] = useState<PrepBrief | null>(null);
    const [prepLoading, setPrepLoading] = useState(false);

    const [selectedConv, setSelectedConv] = useState<string | null>(null);
    const [convMessages, setConvMessages] = useState<MessageItem[]>([]);
    const [convSummary, setConvSummary] = useState<SessionSummary | null>(null);

    const [noteBody, setNoteBody] = useState("");
    const [noteTags, setNoteTags] = useState("");

    const [showPlanDialog, setShowPlanDialog] = useState(false);
    const [planForm, setPlanForm] = useState({ title: "", primary_concern: "", interventions: "" });

    const [showHomeworkDialog, setShowHomeworkDialog] = useState(false);
    const [hwForm, setHwForm] = useState({ title: "", description: "", due_at: "" });

    const [showCrisisDialog, setShowCrisisDialog] = useState(false);
    const [crisisSeverity, setCrisisSeverity] = useState<"low" | "medium" | "high" | "critical">("medium");
    const [crisisContext, setCrisisContext] = useState("");

    const loadPatient = useCallback(async () => {
        if (!patientId) return;
        setLoading(true);
        try {
            const [det, convs, mo, ns, pl, hw, cr] = await Promise.all([
                therapistFetchJson<{
                    patient: { user_id: string; name?: string; email?: string };
                    personality?: Record<string, unknown>;
                    stats?: Record<string, unknown>;
                    link?: { patient_consented_at?: string; created_at?: string; consent_scope?: Record<string, boolean> };
                }>(`/api/therapist/patients/${patientId}`),
                therapistFetchJson<{ conversations: ConversationItem[] }>(`/api/therapist/patients/${patientId}/conversations`),
                therapistFetchJson<{ mood: MoodEntry[] }>(`/api/therapist/patients/${patientId}/mood`),
                therapistFetchJson<{ notes: TherapistNote[] }>(`/api/therapist/notes?patient_id=${patientId}`),
                therapistFetchJson<{ plans: TreatmentPlan[] }>(`/api/therapist/treatment-plans?patient_id=${patientId}`),
                therapistFetchJson<{ homework: HomeworkItem[] }>(`/api/therapist/homework?patient_id=${patientId}`),
                therapistFetchJson<{ events: CrisisEvent[] }>(`/api/therapist/crisis?patient_id=${patientId}`),
            ]);
            setPatient({
                user_id: det.patient?.user_id ?? patientId,
                name: det.patient?.name,
                email: det.patient?.email,
                personality: det.personality,
                stats: det.stats,
                linked_since: det.link?.patient_consented_at || det.link?.created_at,
                consent_scope: det.link?.consent_scope,
            });
            setConversations(convs.conversations || []);
            setMood(mo.mood || []);
            setNotes(ns.notes || []);
            setPlans(pl.plans || []);
            setHomework(hw.homework || []);
            setCrisis(cr.events || []);
        } catch (err: any) {
            toast({ title: "Couldn't load patient", description: err.message, variant: "destructive" });
        } finally {
            setLoading(false);
        }
    }, [patientId, toast]);

    useEffect(() => { loadPatient(); }, [loadPatient]);

    useEffect(() => {
        if (focusEventId && focusEventRef.current) {
            focusEventRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }, [focusEventId, crisis]);

    const openConversation = async (convId: string) => {
        setSelectedConv(convId);
        setConvMessages([]);
        setConvSummary(null);
        try {
            const data = await therapistFetchJson<{ messages: MessageItem[]; summary: SessionSummary | null }>(
                `/api/therapist/patients/${patientId}/conversations/${convId}`
            );
            setConvMessages(data.messages || []);
            setConvSummary(data.summary);
        } catch (err: any) {
            toast({ title: "Couldn't load conversation", description: err.message, variant: "destructive" });
        }
    };

    const loadPrepBrief = async () => {
        setPrepLoading(true);
        try {
            const data = await therapistFetchJson<PrepBrief>(`/api/therapist/patients/${patientId}/prep-brief`);
            setPrepBrief(data);
        } catch (err: any) {
            toast({ title: "Couldn't generate brief", description: err.message, variant: "destructive" });
        } finally {
            setPrepLoading(false);
        }
    };

    const saveNote = async () => {
        if (!noteBody.trim()) return;
        try {
            await therapistFetchJson("/api/therapist/notes", {
                method: "POST",
                body: JSON.stringify({
                    patient_id: patientId,
                    body: noteBody,
                    tags: noteTags.split(",").map((t) => t.trim()).filter(Boolean),
                }),
            });
            setNoteBody("");
            setNoteTags("");
            toast({ title: "Note saved" });
            await loadPatient();
        } catch (err: any) {
            toast({ title: "Save failed", description: err.message, variant: "destructive" });
        }
    };

    const deleteNote = async (noteId: string) => {
        try {
            await therapistFetchJson(`/api/therapist/notes/${noteId}`, { method: "DELETE" });
            await loadPatient();
        } catch (err: any) {
            toast({ title: "Delete failed", description: err.message, variant: "destructive" });
        }
    };

    const createPlan = async () => {
        try {
            await therapistFetchJson("/api/therapist/treatment-plans", {
                method: "POST",
                body: JSON.stringify({
                    patient_id: patientId,
                    title: planForm.title,
                    primary_concern: planForm.primary_concern,
                    interventions: planForm.interventions.split(",").map((s) => s.trim()).filter(Boolean),
                }),
            });
            setPlanForm({ title: "", primary_concern: "", interventions: "" });
            setShowPlanDialog(false);
            toast({ title: "Treatment plan created" });
            await loadPatient();
        } catch (err: any) {
            toast({ title: "Create failed", description: err.message, variant: "destructive" });
        }
    };

    const assignHomework = async () => {
        try {
            await therapistFetchJson("/api/therapist/homework", {
                method: "POST",
                body: JSON.stringify({
                    patient_id: patientId,
                    title: hwForm.title,
                    description: hwForm.description,
                    due_at: hwForm.due_at || null,
                }),
            });
            setHwForm({ title: "", description: "", due_at: "" });
            setShowHomeworkDialog(false);
            toast({ title: "Homework assigned" });
            await loadPatient();
        } catch (err: any) {
            toast({ title: "Assign failed", description: err.message, variant: "destructive" });
        }
    };

    const escalateCrisis = async () => {
        if (!patientId) return;
        try {
            await therapistFetchJson(`/api/therapist/crisis/escalate`, {
                method: "POST",
                body: JSON.stringify({
                    patient_id: patientId,
                    severity: crisisSeverity,
                    notes: crisisContext,
                }),
            });
            setShowCrisisDialog(false);
            setCrisisContext("");
            toast({ title: "Crisis escalated", description: "Event recorded and emergency resources flagged." });
            await loadPatient();
        } catch (err: any) {
            toast({ title: "Escalation failed", description: err.message, variant: "destructive" });
        }
    };

    const resolveCrisis = async (eventId: string) => {
        try {
            await therapistFetchJson(`/api/therapist/crisis/${eventId}/resolve`, { method: "POST" });
            toast({ title: "Crisis resolved", description: "Event marked as closed." });
            await loadPatient();
        } catch (err: any) {
            toast({ title: "Resolve failed", description: err.message, variant: "destructive" });
        }
    };

    const exportPdf = async () => {
        try {
            const res = await therapistFetch(`/api/therapist/patients/${patientId}/export.pdf`);
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `patient-${patientId}-report.pdf`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (err: any) {
            toast({ title: "Export failed", description: err.message, variant: "destructive" });
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-primary/5 via-background to-secondary/10 relative">
            <BackgroundDecor />
            <Navigation />

            <main className="relative z-10 container mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-24 space-y-6">
                <Button variant="ghost" size="sm" onClick={() => navigate("/therapist-portal")}>
                    <ArrowLeft className="h-4 w-4 mr-2" /> Back to portal
                </Button>

                <Card className="rounded-3xl">
                    <CardContent className="p-6 flex items-center justify-between flex-wrap gap-4">
                        <div>
                            <h1 className="text-2xl font-semibold">{patient?.name || patient?.email || patientId}</h1>
                            {patient?.email && <p className="text-sm text-muted-foreground">{patient.email}</p>}
                            {patient?.linked_since && (
                                <p className="text-xs text-muted-foreground mt-1">
                                    Linked since {new Date(patient.linked_since).toLocaleDateString()}
                                </p>
                            )}
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <Button variant="outline" onClick={loadPrepBrief} disabled={prepLoading}>
                                {prepLoading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Brain className="h-4 w-4 mr-2" />}
                                Prep brief
                            </Button>
                            <Button variant="outline" onClick={exportPdf}><Download className="h-4 w-4 mr-2" /> Export PDF</Button>
                            <Button variant="destructive" onClick={() => setShowCrisisDialog(true)}>
                                <AlertTriangle className="h-4 w-4 mr-2" /> Escalate crisis
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {prepBrief && (
                    <Card className="rounded-3xl border-primary/40 bg-primary/5">
                        <CardHeader className="flex-row items-center justify-between">
                            <CardTitle className="flex items-center gap-2 text-base"><Brain className="h-5 w-5" /> Pre-session brief</CardTitle>
                            <Button variant="ghost" size="sm" onClick={() => setPrepBrief(null)}>Dismiss</Button>
                        </CardHeader>
                        <CardContent className="space-y-4 text-sm leading-relaxed">
                            {prepBrief.top_concerns && prepBrief.top_concerns.length > 0 && (
                                <div>
                                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">Top concerns</p>
                                    <ul className="list-disc list-inside space-y-0.5">
                                        {prepBrief.top_concerns.map((c, i) => <li key={i}>{c}</li>)}
                                    </ul>
                                </div>
                            )}
                            {prepBrief.recent_shifts && (
                                <div>
                                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">Recent shifts</p>
                                    <p className="whitespace-pre-wrap">{prepBrief.recent_shifts}</p>
                                </div>
                            )}
                            {prepBrief.unresolved_topics && prepBrief.unresolved_topics.length > 0 && (
                                <div>
                                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">Unresolved topics</p>
                                    <ul className="list-disc list-inside space-y-0.5">
                                        {prepBrief.unresolved_topics.map((t, i) => <li key={i}>{t}</li>)}
                                    </ul>
                                </div>
                            )}
                            {prepBrief.suggested_focus && (
                                <div>
                                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">Suggested focus</p>
                                    <p className="whitespace-pre-wrap">{prepBrief.suggested_focus}</p>
                                </div>
                            )}
                            {prepBrief.risk_notes && (
                                <div className="rounded-xl border border-rose-300 bg-rose-50 dark:bg-rose-950/20 p-3 text-xs text-rose-700 dark:text-rose-300">
                                    <p className="font-semibold mb-1">Risk notes</p>
                                    <p className="whitespace-pre-wrap">{prepBrief.risk_notes}</p>
                                </div>
                            )}
                            {!prepBrief.top_concerns?.length && !prepBrief.recent_shifts && !prepBrief.unresolved_topics?.length && !prepBrief.suggested_focus && !prepBrief.risk_notes && (
                                <p className="text-muted-foreground italic">Not enough prior session data to generate a brief yet.</p>
                            )}
                            <p className="text-[10px] uppercase tracking-widest text-muted-foreground pt-2 border-t">AI draft — review before clinical use</p>
                        </CardContent>
                    </Card>
                )}

                {crisis.some((c) => !c.resolved_at) && (
                    <Card className="rounded-3xl border-rose-300 bg-rose-50 dark:bg-rose-950/20">
                        <CardContent className="p-5 flex items-center gap-3">
                            <AlertTriangle className="h-6 w-6 text-rose-600" />
                            <div className="flex-1">
                                <p className="font-semibold text-rose-700 dark:text-rose-300">Active crisis event</p>
                                <p className="text-sm text-rose-600 dark:text-rose-200">
                                    Review below and coordinate emergency resources with the patient.
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                )}

                <Tabs defaultValue={initialTab} className="space-y-4">
                    <TabsList className="grid grid-cols-6 max-w-4xl">
                        <TabsTrigger value="sessions"><FileText className="h-4 w-4 mr-1" /> Sessions</TabsTrigger>
                        <TabsTrigger value="notes"><StickyNote className="h-4 w-4 mr-1" /> Notes</TabsTrigger>
                        <TabsTrigger value="plans"><ClipboardList className="h-4 w-4 mr-1" /> Plans</TabsTrigger>
                        <TabsTrigger value="homework"><Calendar className="h-4 w-4 mr-1" /> Homework</TabsTrigger>
                        <TabsTrigger value="mood"><Activity className="h-4 w-4 mr-1" /> Mood</TabsTrigger>
                        <TabsTrigger value="crisis"><AlertTriangle className="h-4 w-4 mr-1" /> Crisis</TabsTrigger>
                    </TabsList>

                    <TabsContent value="sessions" className="space-y-4">
                        <div className="grid md:grid-cols-2 gap-4">
                            <Card className="rounded-3xl">
                                <CardHeader>
                                    <CardTitle className="text-base">Session history</CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-2 max-h-[60vh] overflow-y-auto">
                                    {conversations.length === 0 ? (
                                        <p className="text-sm text-muted-foreground text-center py-6">No sessions recorded yet.</p>
                                    ) : conversations.map((c) => (
                                        <button
                                            key={c.conversation_id}
                                            onClick={() => openConversation(c.conversation_id)}
                                            className={`w-full text-left p-3 rounded-xl border transition-colors ${selectedConv === c.conversation_id ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40"}`}
                                        >
                                            <div className="flex items-center justify-between mb-1">
                                                <p className="font-medium text-sm">{c.title || `Session ${c.conversation_id.slice(0, 8)}`}</p>
                                                {c.has_summary && <Badge variant="secondary" className="text-[10px]">SOAP</Badge>}
                                            </div>
                                            <p className="text-xs text-muted-foreground">
                                                {c.started_at ? new Date(c.started_at).toLocaleString() : "—"} · {c.message_count ?? 0} messages
                                            </p>
                                        </button>
                                    ))}
                                </CardContent>
                            </Card>

                            <Card className="rounded-3xl">
                                <CardHeader>
                                    <CardTitle className="text-base">Session detail</CardTitle>
                                    <CardDescription>{selectedConv ? "SOAP summary + transcript" : "Select a session on the left."}</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4 max-h-[60vh] overflow-y-auto">
                                    {!selectedConv ? (
                                        <div className="text-center py-12 text-muted-foreground text-sm">Nothing selected.</div>
                                    ) : (
                                        <>
                                            {convSummary ? (
                                                <div className="space-y-3">
                                                    <p className="text-[10px] uppercase tracking-widest text-muted-foreground">AI-generated SOAP</p>
                                                    <SoapField label="Subjective" value={convSummary.subjective} />
                                                    <SoapField label="Objective" value={convSummary.objective} />
                                                    <SoapField label="Assessment" value={convSummary.assessment} />
                                                    <SoapField label="Plan" value={convSummary.plan} />
                                                    {convSummary.themes && convSummary.themes.length > 0 && (
                                                        <div>
                                                            <p className="text-xs font-medium mb-1">Themes</p>
                                                            <div className="flex flex-wrap gap-1">
                                                                {convSummary.themes.map((t, i) => <Badge key={i} variant="outline" className="text-[10px]">{t}</Badge>)}
                                                            </div>
                                                        </div>
                                                    )}
                                                    {convSummary.risk_flags?.flagged && (
                                                        <div className="rounded-xl border border-rose-300 bg-rose-50 dark:bg-rose-950/20 p-3 text-xs text-rose-700 dark:text-rose-300">
                                                            <strong>Risk flags detected:</strong> {convSummary.risk_flags.severity}
                                                            {convSummary.risk_flags.snippets && convSummary.risk_flags.snippets.length > 0 && (
                                                                <ul className="mt-1 list-disc list-inside">
                                                                    {convSummary.risk_flags.snippets.map((s, i) => <li key={i}>{s}</li>)}
                                                                </ul>
                                                            )}
                                                        </div>
                                                    )}
                                                    <p className="text-[10px] uppercase tracking-widest text-muted-foreground pt-2 border-t">AI draft — review before clinical use</p>
                                                </div>
                                            ) : (
                                                <p className="text-xs text-muted-foreground italic">No SOAP summary generated for this session.</p>
                                            )}
                                            <div className="border-t pt-3 space-y-2">
                                                <p className="text-[10px] uppercase tracking-widest text-muted-foreground">Transcript</p>
                                                {convMessages.map((m) => (
                                                    <div key={m.message_id} className={`text-sm p-3 rounded-xl ${m.role === "user" ? "bg-muted/60" : "bg-primary/5 border border-primary/10"}`}>
                                                        <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">{m.role}</p>
                                                        <p className="whitespace-pre-wrap">{m.content}</p>
                                                    </div>
                                                ))}
                                            </div>
                                        </>
                                    )}
                                </CardContent>
                            </Card>
                        </div>
                    </TabsContent>

                    <TabsContent value="notes" className="space-y-4">
                        <Card className="rounded-3xl">
                            <CardHeader>
                                <CardTitle className="text-base">New private note</CardTitle>
                                <CardDescription>Only you can see these. The patient cannot read your notes.</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <Textarea rows={4} placeholder="Clinical observations, hypotheses, follow-up..." value={noteBody} onChange={(e) => setNoteBody(e.target.value)} />
                                <Input placeholder="Tags (comma-separated)" value={noteTags} onChange={(e) => setNoteTags(e.target.value)} />
                                <div className="flex justify-end">
                                    <Button onClick={saveNote} disabled={!noteBody.trim()}><Plus className="h-4 w-4 mr-2" /> Save note</Button>
                                </div>
                            </CardContent>
                        </Card>

                        <div className="space-y-3">
                            {notes.length === 0 ? (
                                <p className="text-center text-sm text-muted-foreground py-8">No notes yet.</p>
                            ) : notes.map((n) => (
                                <Card key={n.note_id} className="rounded-2xl">
                                    <CardContent className="p-4">
                                        <div className="flex items-start justify-between gap-2 mb-2">
                                            <div className="flex gap-2 flex-wrap">
                                                {(n.tags ?? []).map((t, i) => <Badge key={i} variant="outline" className="text-[10px]">{t}</Badge>)}
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-xs text-muted-foreground">
                                                    {n.created_at && new Date(n.created_at).toLocaleDateString()}
                                                </span>
                                                <Button variant="ghost" size="sm" onClick={() => deleteNote(n.note_id)}>
                                                    <Trash2 className="h-3 w-3" />
                                                </Button>
                                            </div>
                                        </div>
                                        <p className="text-sm whitespace-pre-wrap">{n.body}</p>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </TabsContent>

                    <TabsContent value="plans" className="space-y-4">
                        <div className="flex justify-end">
                            <Button onClick={() => setShowPlanDialog(true)}><Plus className="h-4 w-4 mr-2" /> New plan</Button>
                        </div>
                        {plans.length === 0 ? (
                            <p className="text-center text-sm text-muted-foreground py-8">No treatment plans yet.</p>
                        ) : plans.map((p) => (
                            <Card key={p.plan_id} className="rounded-2xl">
                                <CardHeader>
                                    <div className="flex items-center justify-between">
                                        <CardTitle className="text-base">{p.title}</CardTitle>
                                        <Badge variant={p.status === "active" ? "default" : "outline"}>{p.status}</Badge>
                                    </div>
                                    {p.primary_concern && <CardDescription>{p.primary_concern}</CardDescription>}
                                </CardHeader>
                                <CardContent>
                                    {p.interventions && p.interventions.length > 0 && (
                                        <div className="flex flex-wrap gap-1 mb-2">
                                            {p.interventions.map((i, idx) => <Badge key={idx} variant="secondary" className="text-[10px]">{i}</Badge>)}
                                        </div>
                                    )}
                                    {p.goals && p.goals.length > 0 && (
                                        <ul className="space-y-1 text-sm">
                                            {p.goals.map((g, idx) => (
                                                <li key={idx} className="flex items-start gap-2">
                                                    <span className="text-primary">•</span> {g.goal}
                                                </li>
                                            ))}
                                        </ul>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </TabsContent>

                    <TabsContent value="homework" className="space-y-4">
                        <div className="flex justify-end">
                            <Button onClick={() => setShowHomeworkDialog(true)}><Plus className="h-4 w-4 mr-2" /> Assign homework</Button>
                        </div>
                        {homework.length === 0 ? (
                            <p className="text-center text-sm text-muted-foreground py-8">No homework assigned.</p>
                        ) : homework.map((h) => (
                            <Card key={h.homework_id} className="rounded-2xl">
                                <CardContent className="p-4 flex items-start justify-between gap-3">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-1">
                                            <p className="font-medium">{h.title}</p>
                                            <Badge variant={h.status === "completed" ? "default" : "outline"}>{h.status}</Badge>
                                        </div>
                                        {h.description && <p className="text-sm text-muted-foreground">{h.description}</p>}
                                        {h.due_at && <p className="text-xs text-muted-foreground mt-1">Due {new Date(h.due_at).toLocaleDateString()}</p>}
                                        {h.patient_reflection && (
                                            <div className="mt-3 rounded-xl bg-muted/40 p-3 text-xs">
                                                <p className="font-medium mb-1">Patient reflection:</p>
                                                <p className="whitespace-pre-wrap">{h.patient_reflection}</p>
                                            </div>
                                        )}
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </TabsContent>

                    <TabsContent value="mood" className="space-y-3">
                        {mood.length === 0 ? (
                            <p className="text-center text-sm text-muted-foreground py-8">No mood entries yet.</p>
                        ) : mood.map((m, i) => (
                            <Card key={i} className="rounded-2xl">
                                <CardContent className="p-4 flex items-center gap-4">
                                    <Smile className="h-5 w-5 text-primary" />
                                    <div className="flex-1">
                                        <p className="font-medium">{m.mood ?? "—"}</p>
                                        {m.note && <p className="text-sm text-muted-foreground">{m.note}</p>}
                                    </div>
                                    {m.created_at && <span className="text-xs text-muted-foreground">{new Date(m.created_at).toLocaleDateString()}</span>}
                                </CardContent>
                            </Card>
                        ))}
                    </TabsContent>

                    <TabsContent value="crisis" className="space-y-3">
                        {crisis.length === 0 ? (
                            <p className="text-center text-sm text-muted-foreground py-8">No crisis events logged.</p>
                        ) : crisis.map((c) => {
                            const isFocused = focusEventId === c.event_id;
                            return (
                            <div key={c.event_id} ref={isFocused ? focusEventRef : undefined}>
                                <Card className={`rounded-2xl ${!c.resolved_at ? "border-rose-300" : ""} ${isFocused ? "ring-2 ring-rose-400" : ""}`}>
                                    <CardContent className="p-4 space-y-3">
                                        <div className="flex items-center justify-between gap-2 flex-wrap">
                                            <div className="flex items-center gap-2 flex-wrap">
                                                <Badge variant={c.severity === "critical" || c.severity === "high" ? "destructive" : "outline"}>{c.severity}</Badge>
                                                {typeof c.severity_score === "number" && (
                                                    <Badge variant="outline" className="text-[10px]">score {c.severity_score.toFixed(2)}</Badge>
                                                )}
                                                {c.intervention_type && c.intervention_type !== "modal_shown" && (
                                                    <Badge variant="secondary" className="text-[10px]">{c.intervention_type.replace(/_/g, " ")}</Badge>
                                                )}
                                            </div>
                                            <span className="text-xs text-muted-foreground">{c.created_at && new Date(c.created_at).toLocaleString()}</span>
                                        </div>
                                        <p className="text-xs text-muted-foreground">Triggered by: {c.triggered_by}</p>
                                        {c.trigger_text && (
                                            <div className="rounded-xl border border-border bg-muted/30 p-3">
                                                <p className="text-[11px] uppercase tracking-wide text-muted-foreground mb-1">What triggered this</p>
                                                <p className="text-sm whitespace-pre-wrap">{c.trigger_text}</p>
                                            </div>
                                        )}
                                        {c.keyword_matches && c.keyword_matches.length > 0 && (
                                            <div className="flex flex-wrap gap-1">
                                                {c.keyword_matches.slice(0, 10).map((kw, i) => (
                                                    <Badge key={i} variant="outline" className="text-[10px]">{kw}</Badge>
                                                ))}
                                            </div>
                                        )}
                                        <div className="flex items-center justify-end pt-1">
                                            {c.resolved_at ? (
                                                <Badge variant="secondary">
                                                    Resolved {new Date(c.resolved_at).toLocaleDateString()}
                                                </Badge>
                                            ) : (
                                                <Button size="sm" variant="outline" onClick={() => resolveCrisis(c.event_id)}>
                                                    <CheckCircle2 className="h-4 w-4 mr-1" /> Mark resolved
                                                </Button>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                            );
                        })}
                    </TabsContent>
                </Tabs>
            </main>

            <MobileNavigation />

            {/* Plan dialog */}
            <Dialog open={showPlanDialog} onOpenChange={setShowPlanDialog}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>New treatment plan</DialogTitle>
                        <DialogDescription>Set goals and interventions for this patient.</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-3 py-2">
                        <div>
                            <Label>Title</Label>
                            <Input value={planForm.title} onChange={(e) => setPlanForm({ ...planForm, title: e.target.value })} />
                        </div>
                        <div>
                            <Label>Primary concern</Label>
                            <Input value={planForm.primary_concern} onChange={(e) => setPlanForm({ ...planForm, primary_concern: e.target.value })} />
                        </div>
                        <div>
                            <Label>Interventions (comma-separated)</Label>
                            <Input value={planForm.interventions} onChange={(e) => setPlanForm({ ...planForm, interventions: e.target.value })} placeholder="CBT, behavioral activation" />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="ghost" onClick={() => setShowPlanDialog(false)}>Cancel</Button>
                        <Button onClick={createPlan} disabled={!planForm.title.trim()}>Create</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Homework dialog */}
            <Dialog open={showHomeworkDialog} onOpenChange={setShowHomeworkDialog}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Assign homework</DialogTitle>
                        <DialogDescription>The patient will see this on their dashboard.</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-3 py-2">
                        <div>
                            <Label>Title</Label>
                            <Input value={hwForm.title} onChange={(e) => setHwForm({ ...hwForm, title: e.target.value })} />
                        </div>
                        <div>
                            <Label>Description</Label>
                            <Textarea rows={3} value={hwForm.description} onChange={(e) => setHwForm({ ...hwForm, description: e.target.value })} />
                        </div>
                        <div>
                            <Label>Due date (optional)</Label>
                            <Input type="date" value={hwForm.due_at} onChange={(e) => setHwForm({ ...hwForm, due_at: e.target.value })} />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="ghost" onClick={() => setShowHomeworkDialog(false)}>Cancel</Button>
                        <Button onClick={assignHomework} disabled={!hwForm.title.trim()}>Assign</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Crisis dialog */}
            <Dialog open={showCrisisDialog} onOpenChange={setShowCrisisDialog}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2"><AlertTriangle className="text-rose-600 h-5 w-5" /> Escalate crisis event</DialogTitle>
                        <DialogDescription>
                            This records a crisis event in the patient's timeline and notifies the admin team. If this is a life-threatening emergency, contact local emergency services first.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-3 py-2">
                        <div>
                            <Label>Severity</Label>
                            <Select value={crisisSeverity} onValueChange={(v) => setCrisisSeverity(v as any)}>
                                <SelectTrigger><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="low">Low</SelectItem>
                                    <SelectItem value="medium">Medium</SelectItem>
                                    <SelectItem value="high">High</SelectItem>
                                    <SelectItem value="critical">Critical</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <Label>Context / notes</Label>
                            <Textarea rows={3} value={crisisContext} onChange={(e) => setCrisisContext(e.target.value)} />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="ghost" onClick={() => setShowCrisisDialog(false)}>Cancel</Button>
                        <Button variant="destructive" onClick={escalateCrisis}>Escalate</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}

function SoapField({ label, value }: { label: string; value?: string }) {
    if (!value) return null;
    return (
        <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">{label}</p>
            <p className="text-sm whitespace-pre-wrap">{value}</p>
        </div>
    );
}
