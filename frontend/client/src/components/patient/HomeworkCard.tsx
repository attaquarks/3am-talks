import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { therapistFetchJson } from "@/lib/therapistFetch";
import { HomeworkItem } from "@/types/auth";
import { ClipboardCheck, Calendar, Loader2, CheckCircle2 } from "lucide-react";

export default function HomeworkCard() {
    const { toast } = useToast();
    const [items, setItems] = useState<HomeworkItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState<HomeworkItem | null>(null);
    const [reflection, setReflection] = useState("");
    const [submitting, setSubmitting] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const data = await therapistFetchJson<{ homework: HomeworkItem[] }>("/api/patient/homework");
            setItems(data.homework || []);
        } catch {
            setItems([]);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const markComplete = async () => {
        if (!selected) return;
        setSubmitting(true);
        try {
            await therapistFetchJson(`/api/patient/homework/${selected.homework_id}`, {
                method: "PATCH",
                body: JSON.stringify({ status: "completed", patient_reflection: reflection }),
            });
            toast({ title: "Homework completed", description: "Your therapist will see your reflection." });
            setSelected(null);
            setReflection("");
            await load();
        } catch (err: any) {
            toast({ title: "Couldn't update", description: err.message, variant: "destructive" });
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) return null;
    if (items.length === 0) return null;

    const pending = items.filter((i) => i.status !== "completed" && i.status !== "skipped");

    return (
        <>
            <Card className="animate-fade-in-up">
                <CardHeader className="pb-4">
                    <CardTitle className="flex items-center gap-3 text-2xl">
                        <ClipboardCheck className="h-6 w-6 text-primary" />
                        From your therapist
                    </CardTitle>
                    <CardDescription className="text-base mt-1">
                        {pending.length > 0
                            ? `${pending.length} task${pending.length > 1 ? "s" : ""} waiting for you.`
                            : "All caught up — nice work."}
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {items.slice(0, 4).map((h) => (
                        <button
                            key={h.homework_id}
                            onClick={() => {
                                setSelected(h);
                                setReflection(h.patient_reflection ?? "");
                            }}
                            className="w-full text-left p-5 rounded-2xl border border-border hover:bg-muted/30 transition-colors"
                        >
                            <div className="flex items-start justify-between gap-4">
                                <div className="flex-1">
                                    <p className="font-medium text-lg">{h.title}</p>
                                    {h.description && <p className="text-sm text-muted-foreground mt-1.5 line-clamp-2">{h.description}</p>}
                                    {h.due_at && (
                                        <p className="text-sm text-muted-foreground mt-3 flex items-center gap-1.5">
                                            <Calendar className="h-4 w-4" /> Due {new Date(h.due_at).toLocaleDateString()}
                                        </p>
                                    )}
                                </div>
                                <Badge variant={h.status === "completed" ? "default" : "outline"} className="text-xs shrink-0">
                                    {h.status}
                                </Badge>
                            </div>
                        </button>
                    ))}
                </CardContent>
            </Card>

            <Dialog open={!!selected} onOpenChange={(v) => !v && setSelected(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{selected?.title}</DialogTitle>
                    </DialogHeader>
                    {selected?.description && (
                        <p className="text-sm text-muted-foreground whitespace-pre-wrap">{selected.description}</p>
                    )}
                    <div className="space-y-2">
                        <Label>Your reflection (optional)</Label>
                        <Textarea
                            rows={4}
                            value={reflection}
                            onChange={(e) => setReflection(e.target.value)}
                            placeholder="How did it go? What did you notice?"
                        />
                    </div>
                    <DialogFooter>
                        <Button variant="ghost" onClick={() => setSelected(null)}>Close</Button>
                        <Button onClick={markComplete} disabled={submitting}>
                            {submitting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <CheckCircle2 className="h-4 w-4 mr-2" />}
                            Mark complete
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
