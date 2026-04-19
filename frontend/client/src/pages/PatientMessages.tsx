import { useCallback, useEffect, useRef, useState } from "react";
import { Navigation, MobileNavigation } from "@/components/Navigation";
import BackgroundDecor from "@/components/auth/BackgroundDecor";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/hooks/useAuth";
import { therapistFetchJson } from "@/lib/therapistFetch";
import { SecureMessage } from "@/types/auth";
import { Inbox, Send, Loader2, MessageSquare, HeartHandshake } from "lucide-react";

interface ThreadSummary {
    link_id: string;
    counterparty?: {
        user_id?: string;
        name?: string;
        email?: string;
        display_name?: string;
        title?: string;
    };
    last_message?: SecureMessage | null;
    unread_count?: number;
}

export default function PatientMessages() {
    const { toast } = useToast();
    const { user } = useAuth();

    const [threads, setThreads] = useState<ThreadSummary[]>([]);
    const [selectedLinkId, setSelectedLinkId] = useState<string | null>(null);
    const [threadMessages, setThreadMessages] = useState<SecureMessage[]>([]);
    const [draft, setDraft] = useState("");
    const [loading, setLoading] = useState(true);
    const [threadLoading, setThreadLoading] = useState(false);
    const [sending, setSending] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);

    const loadThreads = useCallback(async () => {
        try {
            const res = await therapistFetchJson<{ threads: ThreadSummary[] }>("/api/therapist/messages");
            setThreads(res.threads || []);
            if (!selectedLinkId && res.threads && res.threads[0]) {
                setSelectedLinkId(res.threads[0].link_id);
            }
        } catch (err: any) {
            toast({ title: "Couldn't load messages", description: err.message, variant: "destructive" });
        } finally {
            setLoading(false);
        }
    }, [toast, selectedLinkId]);

    useEffect(() => { loadThreads(); }, [loadThreads]);

    const loadThread = useCallback(async (linkId: string) => {
        setThreadLoading(true);
        try {
            const data = await therapistFetchJson<{ messages: SecureMessage[] }>(
                `/api/therapist/messages?link_id=${linkId}`
            );
            const msgs = data.messages || [];
            setThreadMessages(msgs);

            const unreadForMe = msgs.filter(
                (m) => m.recipient_id === user?.id && !m.read_at
            );
            if (unreadForMe.length > 0) {
                await Promise.all(
                    unreadForMe.map((m) =>
                        therapistFetchJson(`/api/therapist/messages/${m.message_id}/read`, { method: "POST" })
                            .catch(() => undefined)
                    )
                );
                setThreads((prev) => prev.map((t) => t.link_id === linkId ? { ...t, unread_count: 0 } : t));
            }
        } catch (err: any) {
            toast({ title: "Couldn't open thread", description: err.message, variant: "destructive" });
        } finally {
            setThreadLoading(false);
        }
    }, [toast, user?.id]);

    useEffect(() => {
        if (selectedLinkId) loadThread(selectedLinkId);
        else setThreadMessages([]);
    }, [selectedLinkId, loadThread]);

    useEffect(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [threadMessages]);

    const sendMessage = async () => {
        if (!selectedLinkId || !draft.trim()) return;
        setSending(true);
        try {
            await therapistFetchJson("/api/therapist/messages", {
                method: "POST",
                body: JSON.stringify({ link_id: selectedLinkId, body: draft, urgency: "normal" }),
            });
            setDraft("");
            await Promise.all([loadThreads(), loadThread(selectedLinkId)]);
        } catch (err: any) {
            toast({ title: "Send failed", description: err.message, variant: "destructive" });
        } finally {
            setSending(false);
        }
    };

    const selectedThread = threads.find((t) => t.link_id === selectedLinkId);
    const counterpartyName = selectedThread?.counterparty?.display_name
        || selectedThread?.counterparty?.name
        || selectedThread?.counterparty?.email
        || "Therapist";

    return (
        <div className="min-h-screen bg-gradient-to-br from-primary/10 via-background to-secondary/10 relative">
            <BackgroundDecor />
            <Navigation />

            <main className="relative z-10 container mx-auto px-4 sm:px-6 lg:px-8 py-10 pb-24">
                <div className="flex items-center gap-3 mb-6">
                    <Inbox className="h-7 w-7 text-primary" />
                    <div>
                        <h1 className="text-3xl font-light tracking-tight">Messages</h1>
                        <p className="text-sm text-muted-foreground">Secure conversations with your linked therapists.</p>
                    </div>
                </div>

                {loading ? (
                    <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>
                ) : threads.length === 0 ? (
                    <Card className="rounded-3xl">
                        <CardContent className="p-10 text-center">
                            <div className="mx-auto mb-4 w-16 h-16 rounded-2xl bg-muted flex items-center justify-center">
                                <HeartHandshake className="h-8 w-8 text-muted-foreground" />
                            </div>
                            <h3 className="font-semibold mb-2">No conversations yet</h3>
                            <p className="text-sm text-muted-foreground max-w-md mx-auto">
                                Once a link with a therapist is active, your messages will appear here.
                            </p>
                        </CardContent>
                    </Card>
                ) : (
                    <div className="grid md:grid-cols-[320px_1fr] gap-4">
                        <Card className="rounded-3xl overflow-hidden">
                            <CardHeader><CardTitle className="text-base">Therapists</CardTitle></CardHeader>
                            <CardContent className="p-0 max-h-[70vh] overflow-y-auto">
                                {threads.map((t) => {
                                    const name = t.counterparty?.display_name || t.counterparty?.name || t.counterparty?.email || "Therapist";
                                    const preview = t.last_message?.body ?? "—";
                                    return (
                                        <button
                                            key={t.link_id}
                                            onClick={() => setSelectedLinkId(t.link_id)}
                                            className={`w-full text-left px-4 py-3 border-b border-border last:border-b-0 hover:bg-muted/40 transition-colors ${selectedLinkId === t.link_id ? "bg-primary/5" : ""}`}
                                        >
                                            <div className="flex items-center justify-between">
                                                <p className="font-medium text-sm truncate">{name}</p>
                                                {(t.unread_count ?? 0) > 0 && <Badge className="h-5 px-1.5 text-[10px] shrink-0">{t.unread_count}</Badge>}
                                            </div>
                                            {t.counterparty?.title && <p className="text-[11px] text-muted-foreground truncate">{t.counterparty.title}</p>}
                                            <p className="text-xs text-muted-foreground truncate mt-0.5">{preview}</p>
                                        </button>
                                    );
                                })}
                            </CardContent>
                        </Card>

                        <Card className="rounded-3xl flex flex-col h-[70vh]">
                            {selectedLinkId ? (
                                <>
                                    <CardHeader className="border-b shrink-0">
                                        <CardTitle className="text-base">{counterpartyName}</CardTitle>
                                    </CardHeader>
                                    <CardContent ref={scrollRef} className="flex-1 overflow-y-auto space-y-3 py-4">
                                        {threadLoading ? (
                                            <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-primary" /></div>
                                        ) : threadMessages.length === 0 ? (
                                            <p className="text-center text-sm text-muted-foreground py-12">No messages yet. Say hello.</p>
                                        ) : threadMessages.map((m) => {
                                            const mine = m.sender_id === user?.id;
                                            return (
                                                <div key={m.message_id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                                                    <div className={`max-w-[70%] rounded-2xl px-4 py-3 ${mine ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
                                                        {m.is_system && <Badge variant="secondary" className="mb-1 text-[10px]">System</Badge>}
                                                        {m.urgency && m.urgency !== "normal" && (
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
                                    <p className="text-sm">Select a therapist to view the thread.</p>
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
