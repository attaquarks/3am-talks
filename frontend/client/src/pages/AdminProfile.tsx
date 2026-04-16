import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import BackgroundDecor from "@/components/auth/BackgroundDecor";
import { MobileNavigation, Navigation } from "@/components/Navigation";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";
import { Copy, Mail, Shield, ShieldCheck, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

interface AdminMe {
  user_id: string;
  admin_id: string | null;
  name: string;
  email: string | null;
  role: "admin";
  account_status: string;
  created_at: string | null;
  moderated_at: string | null;
  last_login_at: string | null;
  total_actions: number;
  recent_actions: Array<{
    log_id: string;
    action: string;
    target_user_id: string | null;
    target_resource: string | null;
    reason: string | null;
    created_at: string;
  }>;
}

export default function AdminProfile() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [me, setMe] = useState<AdminMe | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/admin/me");
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data?.detail?.message || data?.message || "Failed to load profile");
      }
      setMe((await response.json()) as AdminMe);
    } catch (error) {
      toast({
        title: "Profile Error",
        description: error instanceof Error ? error.message : "Failed to load admin profile.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    if (!user) return;
    if ((user.role ?? "patient") !== "admin") {
      navigate("/dashboard");
      return;
    }
    void loadMe();
  }, [user, navigate, loadMe]);

  const formatDate = (value: string | null | undefined) => {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "-";
    return date.toLocaleString();
  };

  const copyAdminId = async () => {
    if (!me?.admin_id) return;
    try {
      await navigator.clipboard.writeText(me.admin_id);
      toast({ title: "Copied", description: "Admin ID copied to clipboard." });
    } catch {
      toast({ title: "Copy Failed", variant: "destructive" });
    }
  };

  return (
    <div className="min-h-screen relative flex flex-col bg-gradient-to-br from-primary/10 via-background to-secondary/10 selection:bg-primary/30 overflow-x-hidden">
      <BackgroundDecor />
      <Navigation />

      <main className="container relative z-10 mx-auto px-4 py-8 pb-20 md:pb-8">
        <div className="mb-8 animate-fade-in-up">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-12 h-12 bg-gradient-primary rounded-xl flex items-center justify-center shadow-soft-md">
              <ShieldCheck className="h-6 w-6 text-white" />
            </div>
            <h1 className="text-3xl font-bold text-foreground">Admin Profile</h1>
          </div>
          <p className="text-muted-foreground">Your administrator identity and recent activity.</p>
        </div>

        <div className="grid md:grid-cols-3 gap-6 animate-fade-in-up delay-100">
          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle>Identity</CardTitle>
              <CardDescription>These details follow your admin account across sessions.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="flex items-center justify-between gap-3 p-4 rounded-lg border border-border bg-background/60">
                <div>
                  <p className="text-xs uppercase tracking-widest text-muted-foreground mb-1">Admin ID</p>
                  <p className="text-2xl font-mono font-semibold">{loading ? "…" : me?.admin_id || "Pending"}</p>
                </div>
                <Button size="sm" variant="outline" onClick={copyAdminId} disabled={!me?.admin_id}>
                  <Copy className="h-4 w-4 mr-1" /> Copy
                </Button>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <p className="text-xs uppercase tracking-widest text-muted-foreground mb-1">Name</p>
                  <p className="text-foreground">{me?.name || "—"}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-widest text-muted-foreground mb-1">Email</p>
                  <p className="text-foreground flex items-center gap-2"><Mail className="h-4 w-4 text-muted-foreground" /> {me?.email || "—"}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-widest text-muted-foreground mb-1">Role</p>
                  <Badge variant="outline" className="uppercase">{me?.role || "admin"}</Badge>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-widest text-muted-foreground mb-1">Account Status</p>
                  <Badge>{me?.account_status || "active"}</Badge>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-widest text-muted-foreground mb-1">Joined</p>
                  <p className="text-sm">{formatDate(me?.created_at)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-widest text-muted-foreground mb-1">Last Moderation Action</p>
                  <p className="text-sm">{formatDate(me?.moderated_at)}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Permissions</CardTitle>
              <CardDescription>What this role is authorized to do.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                "Manage user roles and account status",
                "Triage reports and feedback",
                "Approve or reject therapist applications",
                "Compose platform announcements",
                "View immutable audit logs",
              ].map((perm) => (
                <div key={perm} className="flex items-start gap-2">
                  <Shield className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                  <p className="text-sm text-foreground/90">{perm}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <Card className="mt-6 animate-fade-in-up delay-200">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2"><Sparkles className="h-5 w-5" /> Recent Actions</CardTitle>
                <CardDescription>
                  {me ? `You've taken ${me.total_actions} action${me.total_actions === 1 ? "" : "s"} on this platform.` : "Your activity trail."}
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading activity…</p>
            ) : !me || me.recent_actions.length === 0 ? (
              <p className="text-sm text-muted-foreground">No recent actions recorded.</p>
            ) : (
              <div className="space-y-3">
                {me.recent_actions.map((log) => (
                  <div key={log.log_id} className="p-3 rounded-lg border border-border bg-background/60">
                    <div className="flex items-center justify-between gap-3 mb-1">
                      <Badge variant="outline" className="font-mono text-xs">{log.action}</Badge>
                      <p className="text-xs text-muted-foreground">{formatDate(log.created_at)}</p>
                    </div>
                    <p className="text-xs text-muted-foreground break-all">
                      {log.target_user_id || log.target_resource || "—"}
                    </p>
                    {log.reason ? <p className="text-sm mt-1">{log.reason}</p> : null}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </main>

      <MobileNavigation />
    </div>
  );
}
