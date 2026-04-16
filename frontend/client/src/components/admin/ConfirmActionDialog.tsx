import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { AlertTriangle } from "lucide-react";

export interface ConfirmActionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  targetLabel?: string;
  actionLabel: string;
  actionVariant?: "default" | "destructive" | "secondary";
  reasonRequired?: boolean;
  reasonPlaceholder?: string;
  onConfirm: (payload: { reason: string; confirm: string }) => Promise<void> | void;
}

export function ConfirmActionDialog({
  open,
  onOpenChange,
  title,
  description,
  targetLabel,
  actionLabel,
  actionVariant = "destructive",
  reasonRequired = true,
  reasonPlaceholder = "Explain why this action is necessary (saved to audit log)",
  onConfirm,
}: ConfirmActionDialogProps) {
  const [reason, setReason] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      setReason("");
      setConfirmText("");
      setSubmitting(false);
    }
  }, [open]);

  const canSubmit =
    confirmText.trim().toUpperCase() === "CONFIRM" &&
    (!reasonRequired || reason.trim().length > 0) &&
    !submitting;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      await onConfirm({ reason: reason.trim(), confirm: "CONFIRM" });
      onOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-destructive/10 flex items-center justify-center">
              <AlertTriangle className="h-5 w-5 text-destructive" />
            </div>
            <div>
              <DialogTitle>{title}</DialogTitle>
              {targetLabel ? (
                <p className="text-xs text-muted-foreground mt-1 break-all">{targetLabel}</p>
              ) : null}
            </div>
          </div>
          {description ? <DialogDescription className="pt-2">{description}</DialogDescription> : null}
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="admin-action-reason">
              Reason {reasonRequired ? <span className="text-destructive">*</span> : null}
            </Label>
            <Textarea
              id="admin-action-reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder={reasonPlaceholder}
              rows={3}
              required={reasonRequired}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="admin-action-confirm">
              Type <span className="font-mono font-bold text-destructive">CONFIRM</span> to proceed
            </Label>
            <Input
              id="admin-action-confirm"
              value={confirmText}
              onChange={(event) => setConfirmText(event.target.value)}
              placeholder="CONFIRM"
              autoComplete="off"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button variant={actionVariant} onClick={handleSubmit} disabled={!canSubmit}>
            {submitting ? "Working…" : actionLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default ConfirmActionDialog;
