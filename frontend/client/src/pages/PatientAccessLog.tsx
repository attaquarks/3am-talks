import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Navigation, MobileNavigation } from "@/components/Navigation";
import BackgroundDecor from "@/components/auth/BackgroundDecor";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { therapistFetchJson } from "@/lib/therapistFetch";
import { ArrowLeft, History, Loader2, Eye } from "lucide-react";

interface AccessLogEntry {
    log_id?: string;
    therapist_id: string;
    therapist_name?: string;
    resource: string;
    resource_id?: string;
    action: string;
    created_at?: string;
}

export default function PatientAccessLog() {
    const { toast } = useToast();
    const navigate = useNavigate();
    const [entries, setEntries] = useState<AccessLogEntry[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const run = async () => {
            try {
                const data = await therapistFetchJson<{ entries: AccessLogEntry[] }>("/api/patient/access-log");
                setEntries(data.entries || []);
            } catch (err: any) {
                toast({ title: "Couldn't load access log", description: err.message, variant: "destructive" });
            } finally {
                setLoading(false);
            }
        };
        run();
    }, [toast]);

    return (
        <div className="min-h-screen bg-gradient-to-br from-primary/10 via-background to-secondary/10 relative">
            <BackgroundDecor />
            <Navigation />

            <main className="relative z-10 container mx-auto px-4 sm:px-6 lg:px-8 py-10 pb-24 max-w-4xl space-y-6">
                <Button variant="ghost" size="sm" onClick={() => navigate("/my-therapists")}>
                    <ArrowLeft className="h-4 w-4 mr-2" /> Back to My Therapists
                </Button>

                <div className="flex items-center gap-3">
                    <History className="h-7 w-7 text-primary" />
                    <div>
                        <h1 className="text-3xl font-light tracking-tight">Transparency log</h1>
                        <p className="text-sm text-muted-foreground">Every time a linked therapist accessed your data.</p>
                    </div>
                </div>

                <Card className="rounded-3xl">
                    <CardHeader>
                        <CardTitle className="text-base">Recent access events</CardTitle>
                        <CardDescription>Newest first. Entries cannot be edited — this is an append-only record.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {loading ? (
                            <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-primary" /></div>
                        ) : entries.length === 0 ? (
                            <p className="text-center text-sm text-muted-foreground py-8">No access events yet.</p>
                        ) : (
                            entries.map((entry, idx) => (
                                <div key={entry.log_id ?? idx} className="flex items-start justify-between gap-4 p-4 rounded-2xl border border-border bg-muted/20">
                                    <div className="flex items-start gap-3 flex-1 min-w-0">
                                        <div className="h-9 w-9 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
                                            <Eye className="h-4 w-4" />
                                        </div>
                                        <div className="min-w-0">
                                            <p className="font-medium text-sm truncate">
                                                {entry.therapist_name || entry.therapist_id}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                <span className="capitalize">{entry.action}</span> — {entry.resource}
                                                {entry.resource_id && <span className="text-[10px] opacity-60"> ({entry.resource_id.slice(0, 8)})</span>}
                                            </p>
                                        </div>
                                    </div>
                                    <Badge variant="outline" className="text-[10px] shrink-0">
                                        {entry.created_at ? new Date(entry.created_at).toLocaleString() : "—"}
                                    </Badge>
                                </div>
                            ))
                        )}
                    </CardContent>
                </Card>
            </main>

            <MobileNavigation />
        </div>
    );
}
