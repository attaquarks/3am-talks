import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ShieldAlert, Loader2 } from "lucide-react";
import { crisisApi } from "@/lib/crisisApi";
import { useToast } from "@/hooks/use-toast";

interface Props {
    open: boolean;
    seconds: number;
    onClose: () => void;
}

export function CrisisCountdownModal({ open, seconds, onClose }: Props) {
    const [remaining, setRemaining] = useState(seconds);
    const [cancelling, setCancelling] = useState(false);
    const { toast } = useToast();

    useEffect(() => {
        if (!open) return;
        setRemaining(seconds);
        const id = setInterval(() => {
            setRemaining((r) => {
                if (r <= 1) {
                    clearInterval(id);
                    return 0;
                }
                return r - 1;
            });
        }, 1000);
        return () => clearInterval(id);
    }, [open, seconds]);

    const cancel = async () => {
        setCancelling(true);
        try {
            const r = await crisisApi.cancelAlert();
            if (r.cancelled > 0) {
                toast({ title: "Alert cancelled", description: "Your contacts will not be notified." });
            } else {
                toast({ title: "Nothing to cancel", description: "The alert may have already been sent." });
            }
            onClose();
        } catch (err) {
            toast({ title: "Cancel failed", description: String(err), variant: "destructive" });
        } finally {
            setCancelling(false);
        }
    };

    const pct = seconds > 0 ? Math.max(0, (remaining / seconds) * 100) : 0;

    return (
        <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2 text-rose-600">
                        <ShieldAlert className="w-5 h-5" />
                        Sending a safety alert in {remaining}s
                    </DialogTitle>
                    <DialogDescription>
                        We detected you may be in immediate danger. If you're safe, tap the button
                        below to stop the alert from being sent to your emergency contacts.
                    </DialogDescription>
                </DialogHeader>

                <Progress value={pct} className="h-2" />

                <div className="flex flex-col gap-2 pt-2">
                    <Button size="lg" onClick={cancel} disabled={cancelling || remaining === 0}>
                        {cancelling ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                        I'm safe — cancel alert
                    </Button>
                    <p className="text-xs text-muted-foreground text-center">
                        If you do nothing, your contacts will receive a WhatsApp/SMS in {remaining}s.
                    </p>
                </div>
            </DialogContent>
        </Dialog>
    );
}
