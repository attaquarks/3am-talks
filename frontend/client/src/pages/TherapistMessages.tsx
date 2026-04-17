import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigation, MobileNavigation } from "@/components/Navigation";
import BackgroundDecor from "@/components/auth/BackgroundDecor";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/hooks/useAuth";
import { therapistFetchJson } from "@/lib/therapistFetch";
import { CaseloadPatient, SecureMessage } from "@/types/auth";
import { Inbox, Send, Loader2, MessageSquare } from "lucide-react";

export default function TherapistMessages() {
    const { toast } = useToast();
    const { user } = useAuth();
    const [caseload, setCaseload] = useState<CaseloadPatient[]>([]);
    const [messages, setMessages] = useState<SecureMessage[]>([]);
    const [selectedPatient, setSelectedPatient] = useState<string | null>(null);
    const [draft, setDraft] = useState("");
    const [urgency, setUrgency] = useState<"normal" | "priority" | "urgent">("normal");
    const [loading, setLoading] = useState(true);
    const [sending, setSending] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [caseRes, msgRes] = await Promise.all([
                therapistFetchJson<{ patients: CaseloadPatient[] }>("/api/therapist/patients"),
                therapistFetchJson<{ messages: SecureMessage[] }>("/api/therapist/messages"),
            ]);
            setCaseload(caseRes.patients || []);
            setMessages(msgRes.messages || []);
            if (!selectedPatient && caseRes.patients && caseRes.patients[0]) {
                setSelectedPatient(caseRes.patients[0].patient_id);
            }
        } catch (err: any) {
            toast({ title: "Couldn't load messages", description: err.message, variant: "destructive" });
        } finally {
            setLoading(false);
        }
    }, [toast, selectedPatient]);

    useEffect(() => { load(); }, [load]);

    const threadMessages = useMemo(() => {
        if (!selectedPatient) return [];
        return messages
            .filter((m) => m.sender_id === selectedPatient || m.recipient_id === selectedPatient)
            .sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
    }, [messages, selectedPatient]);

    const sendMessage = async () => {
        if (!selectedPatient || !draft.trim()) return;
        setSending(true);
        try {
            await therapistFetchJson("/api/therapist/messages", {
                method: "POST",
                body: JSON.stringify({
                    recipient_id: selectedPatient,
                    body: draft,
                    urgency,
                }),
            });
            setDraft("");
            await load();
        } catch (err: any) {
            toast({ title: "Send failed", description: err.message, variant: "destructive" });
        } finally {
            setSending(false);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-primary/5 via-background to-secondary/10 relative">
            <BackgroundDecor />
            <Navigation />

            <main className="relative z-10 container mx-auto px-4 sm:px-6 lg:px-8 py-10 pb-24">
                <div className="flex items-center gap-3 mb-6">
                    <Inbox className="h-7 w-7 text-primary" />
                    <h1 className="text-3xl font-light tracking-tight">Secure Messages</h1>
                </div>

                {loading ? (
                    <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>
                ) : (
                    <div className="grid md:grid-cols-[320px_1fr] gap-4">
                        <Card className="rounded-3xl overflow-hidden">
                            <CardHeader><CardTitle className="text-base">Patients</CardTitle></CardHeader>
                            <CardContent className="p-0 max-h-[70vh] overflow-y-auto">
                                {caseload.length === 0 ? (
                                    <p className="text-center text-sm text-muted-foreground py-8 px-4">No linked patients yet.</p>
                                ) : caseload.map((p) => {
                                    const unread = messages.filter((m) => m.sender_id === p.patient_id && !m.read_at && m.recipient_id === user?.id).length;
                                    return (
                                        <button
                                            key={p.patient_id}
                                            onClick={() => setSelectedPatient(p.patient_id)}
                                            className={`w-full text-left px-4 py-3 border-b border-border last:border-b-0 hover:bg-muted/40 transition-colors ${selectedPatient === p.patient_id ? "bg-primary/5" : ""}`}
                                        >
                                            <div className="flex items-center justify-between">
                                                <p className="font-medium text-sm">{p.name || p.email || p.patient_id}</p>
                                                {unread > 0 && <Badge className="h-5 px-1.5 text-[10px]">{unread}</Badge>}
                                            </div>
                                            <p className="text-xs text-muted-foreground">{p.email ?? ""}</p>
                                        </button>
                                    );
                                })}
                            </CardContent>
                        </Card>

                        <Card className="rounded-3xl flex flex-col h-[70vh]">
                            {selectedPatient ? (
                                <>
                                    <CardHeader className="border-b shrink-0">
                                        <CardTitle className="text-base">
                                            {caseload.find((p) => p.patient_id === selectedPatient)?.name || "Patient"}
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="flex-1 overflow-y-auto space-y-3 py-4">
                                        {threadMessages.length === 0 ? (
                                            <p className="text-center text-sm text-muted-foreground py-12">No messages yet. Start the conversation.</p>
                                        ) : threadMessages.map((m) => {
                                            const mine = m.sender_id === user?.id;
                                            return (
                                                <div key={m.message_id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                                                    <div className={`max-w-[70%] rounded-2xl px-4 py-3 ${mine ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
                                                        {m.is_system && <Badge variant="secondary" className="mb-1 text-[10px]">System</Badge>}
                                                        {m.urgency !== "normal" && (
                                                            <Badge variant={m.urgency === "urgent" ? "destructive" : "default"} className="mb-1 text-[10px]">
                                                                {m.urgency}
                                                            </Badge>
                                                        )}
                                                        <p className="text-sm whitespace-pre-wrap">{m.body}</p>
                                                        <p className={`text-[10px] mt-1 ${mine ? "text-primary-foreground/70" : "text-muted-foreground"}`}>
                                                            {m.created_at && new Date(m.created_at).toLocaleString()}
                                                        </p>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </CardContent>
                                    <div className="border-t p-4 shrink-0 space-y-2">
                                        <div className="flex gap-2">
                                            <Select value={urgency} onValueChange={(v) => setUrgency(v as any)}>
                                                <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="normal">Normal</SelectItem>
                                                    <SelectItem value="priority">Priority</SelectItem>
                                                    <SelectItem value="urgent">Urgent</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <Textarea
                                            rows={2}
                                            placeholder="Type a message..."
                                            value={draft}
                                            onChange={(e) => setDraft(e.target.value)}
                                        />
                                        <div className="flex justify-end">
                                            <Button onClick={sendMessage} disabled={!draft.trim() || sending}>
                                                {sending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Send className="h-4 w-4 mr-2" />}
                                                Send
                                            </Button>
                                        </div>
                                    </div>
                                </>
                            ) : (
                                <div className="flex flex-col items-center justify-center flex-1 text-muted-foreground">
                                    <MessageSquare className="h-10 w-10 mb-2 opacity-40" />
                                    <p className="text-sm">Select a patient to view the thread.</p>
                                </div>
                            )}
                        </Card>
                    </div>
                )}
            </main>

            <MobileNavigation />
        </div>
    );
}
