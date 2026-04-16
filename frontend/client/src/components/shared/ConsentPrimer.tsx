import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ShieldCheck, Eye, EyeOff, Heart, Brain, FileText, Smile, BookOpen } from "lucide-react";
import { ConsentScope } from "@/types/auth";

interface ConsentPrimerProps {
    open: boolean;
    onClose: () => void;
    onConfirm: (scope: ConsentScope) => Promise<void> | void;
    therapistName?: string;
    initialScope?: ConsentScope;
    title?: string;
    subtitle?: string;
    mode?: "grant" | "review";
}

const DEFAULT_SCOPE: ConsentScope = {
    conversations: true,
    journals: true,
    mood: true,
    reports: true,
    personality: true,
};

const SCOPE_ITEMS: Array<{
    key: keyof ConsentScope;
    label: string;
    description: string;
    icon: typeof Heart;
}> = [
    {
        key: "conversations",
        label: "AI session transcripts",
        description: "Your conversations with Ella, including AI-generated session summaries.",
        icon: BookOpen,
    },
    {
        key: "journals",
        label: "Journal entries",
        description: "Any private journal reflections you have written.",
        icon: FileText,
    },
    {
        key: "mood",
        label: "Mood tracking",
        description: "Daily mood check-ins and long-term trends.",
        icon: Smile,
    },
    {
        key: "reports",
        label: "Progress reports",
        description: "Engagement stats, homework completion, and progress towards goals.",
        icon: Heart,
    },
    {
        key: "personality",
        label: "Personality profile",
        description: "Your personality assessment results used to tailor Ella's tone.",
        icon: Brain,
    },
];

export function ConsentPrimer({
    open,
    onClose,
    onConfirm,
    therapistName,
    initialScope,
    title,
    subtitle,
    mode = "grant",
}: ConsentPrimerProps) {
    const [scope, setScope] = useState<ConsentScope>({ ...DEFAULT_SCOPE, ...(initialScope ?? {}) });
    const [submitting, setSubmitting] = useState(false);
    const [acknowledged, setAcknowledged] = useState(false);

    const toggle = (key: keyof ConsentScope) => {
        setScope((prev) => ({ ...prev, [key]: !prev[key] }));
    };

    const handleConfirm = async () => {
        setSubmitting(true);
        try {
            await onConfirm(scope);
        } finally {
            setSubmitting(false);
        }
    };

    const anySelected = Object.values(scope).some(Boolean);
    const effectiveTitle = title ?? (mode === "grant" ? "Share data with your therapist" : "Data sharing preferences");
    const effectiveSubtitle = subtitle ?? (therapistName
        ? `Choose what ${therapistName} can see. You can revoke access at any time.`
        : "Choose what your therapist can see. You can revoke access at any time.");

    return (
        <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
            <DialogContent className="max-w-2xl max-h-[92vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-3 text-xl">
                        <ShieldCheck className="h-6 w-6 text-primary" />
                        {effectiveTitle}
                    </DialogTitle>
                    <DialogDescription className="text-sm leading-relaxed pt-2">
                        {effectiveSubtitle}
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-3 py-4">
                    {SCOPE_ITEMS.map((item) => {
                        const enabled = !!scope[item.key];
                        return (
                            <button
                                key={item.key}
                                type="button"
                                onClick={() => toggle(item.key)}
                                className={`w-full text-left p-4 rounded-2xl border transition-all ${enabled
                                    ? 'border-primary/40 bg-primary/5 shadow-sm'
                                    : 'border-border bg-muted/30 hover:bg-muted/50'
                                    }`}
                            >
                                <div className="flex items-start gap-4">
                                    <div className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 ${enabled ? 'bg-primary/20 text-primary' : 'bg-muted text-muted-foreground'}`}>
                                        <item.icon className="h-5 w-5" />
                                    </div>
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="font-semibold text-sm">{item.label}</span>
                                            {enabled ? (
                                                <Eye className="h-3.5 w-3.5 text-primary" />
                                            ) : (
                                                <EyeOff className="h-3.5 w-3.5 text-muted-foreground" />
                                            )}
                                        </div>
                                        <p className="text-xs text-muted-foreground leading-relaxed">{item.description}</p>
                                    </div>
                                    <Checkbox checked={enabled} />
                                </div>
                            </button>
                        );
                    })}
                </div>

                <div className="rounded-2xl border border-amber-200 bg-amber-50 dark:border-amber-900/40 dark:bg-amber-950/20 px-4 py-3 text-xs leading-relaxed text-amber-900 dark:text-amber-200">
                    <strong className="block mb-1">What your therapist cannot see:</strong>
                    Any category you turn off above, plus anything you never share with Ella. Therapist private notes are also hidden from you.
                </div>

                {mode === "grant" && (
                    <label className="flex items-start gap-3 px-1 py-2 cursor-pointer">
                        <Checkbox checked={acknowledged} onCheckedChange={(v) => setAcknowledged(!!v)} />
                        <span className="text-xs text-muted-foreground leading-relaxed">
                            I understand that my therapist will see the categories above and that I can revoke access at any time from the "My Therapists" page.
                        </span>
                    </label>
                )}

                <DialogFooter className="gap-2 pt-2">
                    <Button variant="ghost" onClick={onClose} disabled={submitting}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleConfirm}
                        disabled={submitting || !anySelected || (mode === "grant" && !acknowledged)}
                    >
                        {mode === "grant" ? "Confirm & share" : "Save preferences"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

export default ConsentPrimer;
