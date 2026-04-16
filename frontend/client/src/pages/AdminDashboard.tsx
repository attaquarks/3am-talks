import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import BackgroundDecor from "@/components/auth/BackgroundDecor";
import { MobileNavigation, Navigation } from "@/components/Navigation";
import ConfirmActionDialog from "@/components/admin/ConfirmActionDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";
import {
  Activity,
  BadgeCheck,
  Ban,
  Megaphone,
  MessageSquareWarning,
  ScrollText,
  Shield,
  Sparkles,
  Stethoscope,
  Trash2,
  UserCheck,
  Users,
} from "lucide-react";

type UserRole = "patient" | "therapist" | "admin";
type AccountStatus = "active" | "suspended" | "banned";
type ReportStatus = "open" | "in_review" | "resolved" | "dismissed";
type FeedbackStatus = "open" | "reviewed" | "dismissed";
type VerificationStatus = "pending" | "approved" | "rejected";
type AnnouncementAudience = "all" | "patients" | "therapists" | "inactive";

interface AdminUser {
  user_id: string;
  name: string;
  email: string;
  role: UserRole;
  account_status: AccountStatus;
  suspended_until: string | null;
  status_reason: string | null;
  created_at: string | null;
  updated_at: string | null;
  total_sessions: number;
  total_minutes: number;
  mood_improvement_percentage: number;
  last_session_date: string | null;
}

interface AdminReport {
  report_id: string;
  reporter_user_id: string;
  reported_user_id: string | null;
  category: string;
  description: string;
  priority: string;
  status: ReportStatus;
  created_at: string;
}

interface AdminFeedback {
  feedback_id: string;
  user_id: string;
  rating: number | null;
  comment: string;
  status: FeedbackStatus;
  created_at: string;
}

interface AdminOverview {
  total_users: number;
  role_counts: Record<UserRole, number>;
  status_counts: Record<AccountStatus, number>;
  new_users_7d: number;
  conversations_7d: number;
  total_minutes_7d: number;
  open_reports: number;
  pending_feedback: number;
  recent_reports: AdminReport[];
  recent_feedback: AdminFeedback[];
}

interface AdminAnalytics {
  dau: number;
  wau: number;
  mau: number;
  sessions_30d: number;
  total_minutes_30d: number;
  avg_session_minutes: number;
  active_therapists: number;
}

interface AdminAuditLog {
  log_id: string;
  admin_user_id: string;
  admin_id: string | null;
  action: string;
  target_user_id: string | null;
  target_resource: string | null;
  reason: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

interface TherapistVerification {
  verification_id: string;
  user_id: string;
  license_number: string | null;
  license_url: string | null;
  specializations: string[] | null;
  years_of_experience: number | null;
  bio: string | null;
  status: VerificationStatus;
  submitted_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  user_name?: string | null;
  user_email?: string | null;
  user_role?: string | null;
}

interface Announcement {
  announcement_id: string;
  admin_user_id: string;
  title: string;
  body: string;
  audience: AnnouncementAudience;
  active: boolean;
  created_at: string;
  expires_at: string | null;
}

const defaultOverview: AdminOverview = {
  total_users: 0,
  role_counts: { patient: 0, therapist: 0, admin: 0 },
  status_counts: { active: 0, suspended: 0, banned: 0 },
  new_users_7d: 0,
  conversations_7d: 0,
  total_minutes_7d: 0,
  open_reports: 0,
  pending_feedback: 0,
  recent_reports: [],
  recent_feedback: [],
};

const defaultAnalytics: AdminAnalytics = {
  dau: 0,
  wau: 0,
  mau: 0,
  sessions_30d: 0,
  total_minutes_30d: 0,
  avg_session_minutes: 0,
  active_therapists: 0,
};

type PendingAction =
  | { kind: "status"; user: AdminUser; nextStatus: AccountStatus }
  | { kind: "role"; user: AdminUser; nextRole: UserRole }
  | { kind: "delete"; user: AdminUser }
  | { kind: "therapist"; verification: TherapistVerification; decision: "approved" | "rejected" }
  | { kind: "announcement-deactivate"; announcement: Announcement };

export default function AdminDashboard() {
  const { user } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();

  const [overview, setOverview] = useState<AdminOverview>(defaultOverview);
  const [analytics, setAnalytics] = useState<AdminAnalytics>(defaultAnalytics);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [reports, setReports] = useState<AdminReport[]>([]);
  const [feedback, setFeedback] = useState<AdminFeedback[]>([]);
  const [logs, setLogs] = useState<AdminAuditLog[]>([]);
  const [verifications, setVerifications] = useState<TherapistVerification[]>([]);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);

  const [loadingOverview, setLoadingOverview] = useState(true);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [loadingReports, setLoadingReports] = useState(true);
  const [loadingFeedback, setLoadingFeedback] = useState(true);
  const [loadingLogs, setLoadingLogs] = useState(true);
  const [loadingVerifications, setLoadingVerifications] = useState(true);
  const [loadingAnnouncements, setLoadingAnnouncements] = useState(true);

  const [roleFilter, setRoleFilter] = useState<"all" | UserRole>("all");
  const [statusFilter, setStatusFilter] = useState<"all" | AccountStatus>("all");
  const [search, setSearch] = useState("");

  const [reportFilter, setReportFilter] = useState<"all" | ReportStatus>("all");
  const [feedbackFilter, setFeedbackFilter] = useState<"all" | FeedbackStatus>("all");
  const [verificationFilter, setVerificationFilter] = useState<"all" | VerificationStatus>("pending");
  const [logActionFilter, setLogActionFilter] = useState<string>("all");

  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);

  const [announcementTitle, setAnnouncementTitle] = useState("");
  const [announcementBody, setAnnouncementBody] = useState("");
  const [announcementAudience, setAnnouncementAudience] = useState<AnnouncementAudience>("all");
  const [creatingAnnouncement, setCreatingAnnouncement] = useState(false);

  const adminFetch = useCallback(async (endpoint: string, options: RequestInit = {}) => {
    const response = await fetch(endpoint, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const message = errorData?.detail?.message || errorData?.message || "Admin request failed";
      throw new Error(message);
    }

    return response;
  }, []);

  const loadOverview = useCallback(async () => {
    setLoadingOverview(true);
    try {
      const [overviewRes, analyticsRes] = await Promise.all([
        adminFetch("/api/admin/overview"),
        adminFetch("/api/admin/analytics"),
      ]);
      setOverview((await overviewRes.json()) as AdminOverview);
      setAnalytics((await analyticsRes.json()) as AdminAnalytics);
    } catch (error) {
      toast({
        title: "Admin Overview Error",
        description: error instanceof Error ? error.message : "Failed to load overview.",
        variant: "destructive",
      });
    } finally {
      setLoadingOverview(false);
    }
  }, [adminFetch, toast]);

  const loadUsers = useCallback(async () => {
    setLoadingUsers(true);
    try {
      const params = new URLSearchParams();
      params.set("role", roleFilter);
      params.set("status", statusFilter);
      if (search.trim()) params.set("search", search.trim());
      const response = await adminFetch(`/api/admin/users?${params.toString()}`);
      const data = (await response.json()) as { users: AdminUser[] };
      setUsers(data.users ?? []);
    } catch (error) {
      toast({
        title: "User Oversight Error",
        description: error instanceof Error ? error.message : "Failed to load users.",
        variant: "destructive",
      });
    } finally {
      setLoadingUsers(false);
    }
  }, [adminFetch, roleFilter, search, statusFilter, toast]);

  const loadReports = useCallback(async () => {
    setLoadingReports(true);
    try {
      const response = await adminFetch("/api/admin/reports");
      const data = (await response.json()) as { reports: AdminReport[] };
      setReports(data.reports ?? []);
    } catch (error) {
      toast({
        title: "Reports Error",
        description: error instanceof Error ? error.message : "Failed to load reports.",
        variant: "destructive",
      });
    } finally {
      setLoadingReports(false);
    }
  }, [adminFetch, toast]);

  const loadFeedback = useCallback(async () => {
    setLoadingFeedback(true);
    try {
      const response = await adminFetch("/api/admin/feedback");
      const data = (await response.json()) as { feedback: AdminFeedback[] };
      setFeedback(data.feedback ?? []);
    } catch (error) {
      toast({
        title: "Feedback Error",
        description: error instanceof Error ? error.message : "Failed to load feedback.",
        variant: "destructive",
      });
    } finally {
      setLoadingFeedback(false);
    }
  }, [adminFetch, toast]);

  const loadLogs = useCallback(async () => {
    setLoadingLogs(true);
    try {
      const params = new URLSearchParams();
      if (logActionFilter !== "all") params.set("action", logActionFilter);
      const response = await adminFetch(`/api/admin/logs?${params.toString()}`);
      const data = (await response.json()) as { logs: AdminAuditLog[] };
      setLogs(data.logs ?? []);
    } catch (error) {
      toast({
        title: "Audit Log Error",
        description: error instanceof Error ? error.message : "Failed to load audit logs.",
        variant: "destructive",
      });
    } finally {
      setLoadingLogs(false);
    }
  }, [adminFetch, logActionFilter, toast]);

  const loadVerifications = useCallback(async () => {
    setLoadingVerifications(true);
    try {
      const params = new URLSearchParams();
      params.set("status", verificationFilter);
      const response = await adminFetch(`/api/admin/therapists/queue?${params.toString()}`);
      const data = (await response.json()) as { queue: TherapistVerification[] };
      setVerifications(data.queue ?? []);
    } catch (error) {
      toast({
        title: "Therapist Queue Error",
        description: error instanceof Error ? error.message : "Failed to load verifications.",
        variant: "destructive",
      });
    } finally {
      setLoadingVerifications(false);
    }
  }, [adminFetch, verificationFilter, toast]);

  const loadAnnouncements = useCallback(async () => {
    setLoadingAnnouncements(true);
    try {
      const response = await adminFetch("/api/admin/announcements");
      const data = (await response.json()) as { announcements: Announcement[] };
      setAnnouncements(data.announcements ?? []);
    } catch (error) {
      toast({
        title: "Announcements Error",
        description: error instanceof Error ? error.message : "Failed to load announcements.",
        variant: "destructive",
      });
    } finally {
      setLoadingAnnouncements(false);
    }
  }, [adminFetch, toast]);

  useEffect(() => {
    if (!user) return;
    if ((user.role ?? "patient") !== "admin") {
      navigate("/dashboard");
      return;
    }
    void loadOverview();
    void loadUsers();
    void loadReports();
    void loadFeedback();
    void loadLogs();
    void loadVerifications();
    void loadAnnouncements();
  }, [user, navigate, loadOverview, loadUsers, loadReports, loadFeedback, loadLogs, loadVerifications, loadAnnouncements]);

  useEffect(() => {
    if ((user?.role ?? "patient") !== "admin") return;
    const timeout = setTimeout(() => {
      void loadUsers();
    }, 250);
    return () => clearTimeout(timeout);
  }, [roleFilter, statusFilter, search, user?.role, loadUsers]);

  useEffect(() => {
    if ((user?.role ?? "patient") !== "admin") return;
    void loadVerifications();
  }, [verificationFilter, user?.role, loadVerifications]);

  useEffect(() => {
    if ((user?.role ?? "patient") !== "admin") return;
    void loadLogs();
  }, [logActionFilter, user?.role, loadLogs]);

  const filteredReports = useMemo(() => {
    if (reportFilter === "all") return reports;
    return reports.filter((report) => report.status === reportFilter);
  }, [reports, reportFilter]);

  const filteredFeedback = useMemo(() => {
    if (feedbackFilter === "all") return feedback;
    return feedback.filter((item) => item.status === feedbackFilter);
  }, [feedback, feedbackFilter]);

  const runStatusUpdate = async (targetUser: AdminUser, status: AccountStatus, reason: string) => {
    await adminFetch(`/api/admin/users/${targetUser.user_id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, reason, confirm: "CONFIRM" }),
    });
    toast({ title: "Status Updated", description: `${targetUser.name} is now ${status}.` });
    await Promise.all([loadUsers(), loadOverview(), loadLogs()]);
  };

  const runRoleUpdate = async (targetUser: AdminUser, role: UserRole, reason: string) => {
    await adminFetch(`/api/admin/users/${targetUser.user_id}/role`, {
      method: "PATCH",
      body: JSON.stringify({ role, reason, confirm: "CONFIRM" }),
    });
    toast({ title: "Role Updated", description: `${targetUser.name} is now ${role}.` });
    await Promise.all([loadUsers(), loadOverview(), loadLogs()]);
  };

  const runDeleteUser = async (targetUser: AdminUser, reason: string) => {
    await adminFetch(`/api/admin/users/${targetUser.user_id}`, {
      method: "DELETE",
      body: JSON.stringify({ reason, confirm: "CONFIRM" }),
    });
    toast({ title: "User Deleted", description: `${targetUser.name} has been removed.` });
    await Promise.all([loadUsers(), loadOverview(), loadLogs()]);
  };

  const runTherapistReview = async (
    verification: TherapistVerification,
    status: "approved" | "rejected",
    notes: string,
  ) => {
    await adminFetch(`/api/admin/therapists/${verification.verification_id}`, {
      method: "PATCH",
      body: JSON.stringify({ status, review_notes: notes }),
    });
    toast({
      title: status === "approved" ? "Therapist Approved" : "Therapist Rejected",
      description: verification.user_name || verification.user_id,
    });
    await Promise.all([loadVerifications(), loadOverview(), loadLogs(), loadUsers()]);
  };

  const runAnnouncementDeactivate = async (announcement: Announcement) => {
    await adminFetch(`/api/admin/announcements/${announcement.announcement_id}`, {
      method: "DELETE",
    });
    toast({ title: "Announcement Deactivated", description: announcement.title });
    await Promise.all([loadAnnouncements(), loadLogs()]);
  };

  const handleConfirm = async ({ reason }: { reason: string; confirm: string }) => {
    if (!pendingAction) return;
    try {
      switch (pendingAction.kind) {
        case "status":
          await runStatusUpdate(pendingAction.user, pendingAction.nextStatus, reason);
          break;
        case "role":
          await runRoleUpdate(pendingAction.user, pendingAction.nextRole, reason);
          break;
        case "delete":
          await runDeleteUser(pendingAction.user, reason);
          break;
        case "therapist":
          await runTherapistReview(pendingAction.verification, pendingAction.decision, reason);
          break;
        case "announcement-deactivate":
          await runAnnouncementDeactivate(pendingAction.announcement);
          break;
      }
      setPendingAction(null);
    } catch (error) {
      toast({
        title: "Action Failed",
        description: error instanceof Error ? error.message : "Unable to complete action.",
        variant: "destructive",
      });
      throw error;
    }
  };

  const handleReportStatus = async (reportId: string, status: ReportStatus) => {
    try {
      await adminFetch(`/api/admin/reports/${reportId}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      toast({ title: "Report Updated", description: `Report moved to ${status}.` });
      await Promise.all([loadReports(), loadOverview()]);
    } catch (error) {
      toast({
        title: "Report Update Failed",
        description: error instanceof Error ? error.message : "Unable to update report.",
        variant: "destructive",
      });
    }
  };

  const handleFeedbackStatus = async (feedbackId: string, status: FeedbackStatus) => {
    try {
      await adminFetch(`/api/admin/feedback/${feedbackId}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      toast({ title: "Feedback Updated", description: `Feedback marked as ${status}.` });
      await Promise.all([loadFeedback(), loadOverview()]);
    } catch (error) {
      toast({
        title: "Feedback Update Failed",
        description: error instanceof Error ? error.message : "Unable to update feedback.",
        variant: "destructive",
      });
    }
  };

  const handleCreateAnnouncement = async () => {
    if (!announcementTitle.trim() || !announcementBody.trim()) {
      toast({
        title: "Missing Fields",
        description: "Title and body are required.",
        variant: "destructive",
      });
      return;
    }
    setCreatingAnnouncement(true);
    try {
      await adminFetch("/api/admin/announcements", {
        method: "POST",
        body: JSON.stringify({
          title: announcementTitle.trim(),
          body: announcementBody.trim(),
          audience: announcementAudience,
        }),
      });
      toast({ title: "Announcement Published" });
      setAnnouncementTitle("");
      setAnnouncementBody("");
      setAnnouncementAudience("all");
      await Promise.all([loadAnnouncements(), loadLogs()]);
    } catch (error) {
      toast({
        title: "Announcement Failed",
        description: error instanceof Error ? error.message : "Unable to publish announcement.",
        variant: "destructive",
      });
    } finally {
      setCreatingAnnouncement(false);
    }
  };

  const formatDate = (value: string | null | undefined) => {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "-";
    return date.toLocaleString();
  };

  const statusBadgeVariant = (status: AccountStatus) => {
    if (status === "active") return "default" as const;
    if (status === "suspended") return "secondary" as const;
    return "destructive" as const;
  };

  const reportBadgeVariant = (status: ReportStatus) => {
    if (status === "open") return "destructive" as const;
    if (status === "in_review") return "secondary" as const;
    return "outline" as const;
  };

  const feedbackBadgeVariant = (status: FeedbackStatus) => {
    if (status === "open") return "secondary" as const;
    if (status === "reviewed") return "default" as const;
    return "outline" as const;
  };

  const verificationBadgeVariant = (status: VerificationStatus) => {
    if (status === "pending") return "secondary" as const;
    if (status === "approved") return "default" as const;
    return "destructive" as const;
  };

  const confirmDialogConfig = useMemo(() => {
    if (!pendingAction) return null;

    switch (pendingAction.kind) {
      case "status": {
        const { user: target, nextStatus } = pendingAction;
        const titleMap: Record<AccountStatus, string> = {
          active: "Reactivate Account",
          suspended: "Suspend Account",
          banned: "Ban Account",
        };
        return {
          title: titleMap[nextStatus],
          description: `This will change ${target.name}'s account status. The reason will be written to the admin audit log.`,
          targetLabel: `${target.name} • ${target.email || target.user_id}`,
          actionLabel: titleMap[nextStatus],
          actionVariant: nextStatus === "active" ? ("default" as const) : ("destructive" as const),
        };
      }
      case "role": {
        const { user: target, nextRole } = pendingAction;
        return {
          title: `Change Role to ${nextRole}`,
          description: `This updates ${target.name}'s platform role. Admin promotions auto-assign an Admin ID.`,
          targetLabel: `${target.name} • currently ${target.role}`,
          actionLabel: `Set role to ${nextRole}`,
          actionVariant: "secondary" as const,
        };
      }
      case "delete": {
        const { user: target } = pendingAction;
        return {
          title: "Delete User",
          description: "This permanently removes the user's profile. This action cannot be undone.",
          targetLabel: `${target.name} • ${target.email || target.user_id}`,
          actionLabel: "Delete Permanently",
          actionVariant: "destructive" as const,
        };
      }
      case "therapist": {
        const { verification, decision } = pendingAction;
        return {
          title: decision === "approved" ? "Approve Therapist" : "Reject Therapist",
          description:
            decision === "approved"
              ? "Approval promotes this user to the therapist role and marks the application verified."
              : "Rejection keeps the user as a patient and records the rejection reason.",
          targetLabel: `${verification.user_name || verification.user_id} • ${verification.user_email || ""}`,
          actionLabel: decision === "approved" ? "Approve" : "Reject",
          actionVariant: decision === "approved" ? ("default" as const) : ("destructive" as const),
        };
      }
      case "announcement-deactivate": {
        const { announcement } = pendingAction;
        return {
          title: "Deactivate Announcement",
          description: "This hides the announcement from all targeted users.",
          targetLabel: announcement.title,
          actionLabel: "Deactivate",
          actionVariant: "destructive" as const,
        };
      }
    }
  }, [pendingAction]);

  const uniqueLogActions = useMemo(() => {
    const set = new Set<string>();
    logs.forEach((log) => set.add(log.action));
    return Array.from(set).sort();
  }, [logs]);

  return (
    <div className="min-h-screen relative flex flex-col bg-gradient-to-br from-primary/10 via-background to-secondary/10 selection:bg-primary/30 overflow-x-hidden">
      <BackgroundDecor />
      <Navigation />

      <main className="container relative z-10 mx-auto px-4 py-8 pb-20 md:pb-8">
        <div className="mb-8 animate-fade-in-up">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-12 h-12 bg-gradient-primary rounded-xl flex items-center justify-center shadow-soft-md">
              <Shield className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-foreground">Admin Control Center</h1>
              {user?.admin_id ? (
                <p className="text-sm text-muted-foreground font-mono">
                  Signed in as <span className="text-foreground">{user.admin_id}</span>
                </p>
              ) : null}
            </div>
          </div>
          <p className="text-muted-foreground">
            Oversee users, triage reports, verify therapists, and keep platform operations healthy.
          </p>
        </div>

        <div className="grid md:grid-cols-4 gap-4 mb-8 animate-fade-in-up delay-100">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold text-foreground">{loadingOverview ? "..." : overview.total_users}</p>
                  <p className="text-sm text-muted-foreground">Total Users</p>
                </div>
                <Users className="h-8 w-8 text-primary" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold text-foreground">{loadingOverview ? "..." : analytics.dau}</p>
                  <p className="text-sm text-muted-foreground">DAU</p>
                </div>
                <Activity className="h-8 w-8 text-secondary" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold text-foreground">{loadingOverview ? "..." : overview.open_reports}</p>
                  <p className="text-sm text-muted-foreground">Open Reports</p>
                </div>
                <MessageSquareWarning className="h-8 w-8 text-destructive" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold text-foreground">{loadingOverview ? "..." : overview.pending_feedback}</p>
                  <p className="text-sm text-muted-foreground">Pending Feedback</p>
                </div>
                <Sparkles className="h-8 w-8 text-accent" />
              </div>
            </CardContent>
          </Card>
        </div>

        <Tabs defaultValue="overview" className="w-full animate-fade-in-up delay-200">
          <TabsList className="grid w-full grid-cols-3 md:grid-cols-7">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="users">Users</TabsTrigger>
            <TabsTrigger value="therapists">Therapists</TabsTrigger>
            <TabsTrigger value="reports">Reports</TabsTrigger>
            <TabsTrigger value="feedback">Feedback</TabsTrigger>
            <TabsTrigger value="announcements">Announcements</TabsTrigger>
            <TabsTrigger value="logs">Audit Logs</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            <div className="grid md:grid-cols-3 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Role Distribution</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between"><span>Patients</span><Badge>{overview.role_counts.patient}</Badge></div>
                  <div className="flex items-center justify-between"><span>Therapists</span><Badge variant="secondary">{overview.role_counts.therapist}</Badge></div>
                  <div className="flex items-center justify-between"><span>Admins</span><Badge variant="outline">{overview.role_counts.admin}</Badge></div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Account Health</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between"><span>Active</span><Badge>{overview.status_counts.active}</Badge></div>
                  <div className="flex items-center justify-between"><span>Suspended</span><Badge variant="secondary">{overview.status_counts.suspended}</Badge></div>
                  <div className="flex items-center justify-between"><span>Banned</span><Badge variant="destructive">{overview.status_counts.banned}</Badge></div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Engagement</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between"><span>WAU</span><Badge variant="outline">{analytics.wau}</Badge></div>
                  <div className="flex items-center justify-between"><span>MAU</span><Badge variant="outline">{analytics.mau}</Badge></div>
                  <div className="flex items-center justify-between"><span>Avg session (min)</span><Badge variant="outline">{analytics.avg_session_minutes}</Badge></div>
                  <div className="flex items-center justify-between"><span>Active therapists</span><Badge variant="outline">{analytics.active_therapists}</Badge></div>
                </CardContent>
              </Card>
            </div>

            <div className="grid lg:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Recent Reports</CardTitle>
                  <CardDescription>Most recent moderation queue items.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {overview.recent_reports.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No reports available.</p>
                  ) : (
                    overview.recent_reports.map((report) => (
                      <div key={report.report_id} className="p-3 rounded-lg border border-border bg-background/60">
                        <div className="flex items-center justify-between gap-2 mb-2">
                          <p className="text-sm font-semibold capitalize">{report.category}</p>
                          <Badge variant={reportBadgeVariant(report.status)}>{report.status}</Badge>
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-2">{report.description}</p>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Recent Feedback</CardTitle>
                  <CardDescription>Latest user feedback submissions.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {overview.recent_feedback.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No feedback available.</p>
                  ) : (
                    overview.recent_feedback.map((item) => (
                      <div key={item.feedback_id} className="p-3 rounded-lg border border-border bg-background/60">
                        <div className="flex items-center justify-between gap-2 mb-2">
                          <p className="text-sm font-semibold">Rating: {item.rating ?? "-"}</p>
                          <Badge variant={feedbackBadgeVariant(item.status)}>{item.status}</Badge>
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-2">{item.comment}</p>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="users" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>User Oversight</CardTitle>
                <CardDescription>Every destructive action requires a reason and CONFIRM token — it is logged.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid md:grid-cols-3 gap-3 mb-4">
                  <Input
                    placeholder="Search by name, email, or user ID"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                  />
                  <Select value={roleFilter} onValueChange={(value: "all" | UserRole) => setRoleFilter(value)}>
                    <SelectTrigger><SelectValue placeholder="Filter by role" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Roles</SelectItem>
                      <SelectItem value="patient">Patients</SelectItem>
                      <SelectItem value="therapist">Therapists</SelectItem>
                      <SelectItem value="admin">Admins</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={statusFilter} onValueChange={(value: "all" | AccountStatus) => setStatusFilter(value)}>
                    <SelectTrigger><SelectValue placeholder="Filter by status" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Statuses</SelectItem>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="suspended">Suspended</SelectItem>
                      <SelectItem value="banned">Banned</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="rounded-lg border border-border overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>User</TableHead>
                        <TableHead>Role</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Analytics</TableHead>
                        <TableHead>Joined</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {loadingUsers ? (
                        <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">Loading users...</TableCell></TableRow>
                      ) : users.length === 0 ? (
                        <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">No users matched the selected filters.</TableCell></TableRow>
                      ) : (
                        users.map((portalUser) => (
                          <TableRow key={portalUser.user_id}>
                            <TableCell>
                              <p className="font-semibold text-foreground">{portalUser.name || "User"}</p>
                              <p className="text-xs text-muted-foreground break-all">{portalUser.email || portalUser.user_id}</p>
                            </TableCell>
                            <TableCell>
                              <Select
                                value={portalUser.role}
                                onValueChange={(value: UserRole) => {
                                  if (value !== portalUser.role) {
                                    setPendingAction({ kind: "role", user: portalUser, nextRole: value });
                                  }
                                }}
                              >
                                <SelectTrigger className="w-[140px]"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="patient">Patient</SelectItem>
                                  <SelectItem value="therapist">Therapist</SelectItem>
                                  <SelectItem value="admin">Admin</SelectItem>
                                </SelectContent>
                              </Select>
                            </TableCell>
                            <TableCell>
                              <div className="space-y-1">
                                <Badge variant={statusBadgeVariant(portalUser.account_status)}>{portalUser.account_status}</Badge>
                                {portalUser.suspended_until && portalUser.account_status === "suspended" ? (
                                  <p className="text-xs text-muted-foreground">Until {formatDate(portalUser.suspended_until)}</p>
                                ) : null}
                              </div>
                            </TableCell>
                            <TableCell>
                              <p className="text-sm">{portalUser.total_sessions} sessions</p>
                              <p className="text-xs text-muted-foreground">{portalUser.total_minutes} min</p>
                            </TableCell>
                            <TableCell>{formatDate(portalUser.created_at)}</TableCell>
                            <TableCell>
                              <div className="flex flex-wrap gap-2">
                                <Button size="sm" variant="outline" onClick={() => setPendingAction({ kind: "status", user: portalUser, nextStatus: "active" })}>Activate</Button>
                                <Button size="sm" variant="secondary" onClick={() => setPendingAction({ kind: "status", user: portalUser, nextStatus: "suspended" })}>Suspend</Button>
                                <Button size="sm" variant="destructive" onClick={() => setPendingAction({ kind: "status", user: portalUser, nextStatus: "banned" })}>Ban</Button>
                                <Button size="sm" variant="ghost" onClick={() => setPendingAction({ kind: "delete", user: portalUser })}>
                                  <Trash2 className="h-3.5 w-3.5 mr-1" /> Delete
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="therapists" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Stethoscope className="h-5 w-5" /> Therapist Verification Queue</CardTitle>
                <CardDescription>Review license submissions. Approvals promote the user to the therapist role.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="mb-4">
                  <Select value={verificationFilter} onValueChange={(value: "all" | VerificationStatus) => setVerificationFilter(value)}>
                    <SelectTrigger className="w-[220px]"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Submissions</SelectItem>
                      <SelectItem value="pending">Pending</SelectItem>
                      <SelectItem value="approved">Approved</SelectItem>
                      <SelectItem value="rejected">Rejected</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="rounded-lg border border-border overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Applicant</TableHead>
                        <TableHead>License</TableHead>
                        <TableHead>Specializations</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Submitted</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {loadingVerifications ? (
                        <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">Loading queue...</TableCell></TableRow>
                      ) : verifications.length === 0 ? (
                        <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">No verifications in this queue.</TableCell></TableRow>
                      ) : (
                        verifications.map((verification) => (
                          <TableRow key={verification.verification_id}>
                            <TableCell>
                              <p className="font-semibold">{verification.user_name || "Applicant"}</p>
                              <p className="text-xs text-muted-foreground break-all">{verification.user_email || verification.user_id}</p>
                            </TableCell>
                            <TableCell>
                              {verification.license_url ? (
                                <a href={verification.license_url} target="_blank" rel="noreferrer" className="text-primary underline text-sm">
                                  View license
                                </a>
                              ) : (
                                <span className="text-xs text-muted-foreground">{verification.license_number || "Not provided"}</span>
                              )}
                            </TableCell>
                            <TableCell>
                              <div className="flex flex-wrap gap-1">
                                {(verification.specializations || []).map((spec) => (
                                  <Badge key={spec} variant="outline" className="text-xs">{spec}</Badge>
                                ))}
                                {(!verification.specializations || verification.specializations.length === 0) && (
                                  <span className="text-xs text-muted-foreground">—</span>
                                )}
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge variant={verificationBadgeVariant(verification.status)}>{verification.status}</Badge>
                            </TableCell>
                            <TableCell>{formatDate(verification.submitted_at)}</TableCell>
                            <TableCell>
                              <div className="flex flex-wrap gap-2">
                                <Button
                                  size="sm"
                                  variant="default"
                                  disabled={verification.status === "approved"}
                                  onClick={() => setPendingAction({ kind: "therapist", verification, decision: "approved" })}
                                >
                                  <BadgeCheck className="h-3.5 w-3.5 mr-1" /> Approve
                                </Button>
                                <Button
                                  size="sm"
                                  variant="destructive"
                                  disabled={verification.status === "rejected"}
                                  onClick={() => setPendingAction({ kind: "therapist", verification, decision: "rejected" })}
                                >
                                  Reject
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="reports" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Reports Queue</CardTitle>
                <CardDescription>Review reports and update moderation status.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="mb-4">
                  <Select value={reportFilter} onValueChange={(value: "all" | ReportStatus) => setReportFilter(value)}>
                    <SelectTrigger className="w-[220px]"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Report Statuses</SelectItem>
                      <SelectItem value="open">Open</SelectItem>
                      <SelectItem value="in_review">In Review</SelectItem>
                      <SelectItem value="resolved">Resolved</SelectItem>
                      <SelectItem value="dismissed">Dismissed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="rounded-lg border border-border overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Category</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead>Priority</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {loadingReports ? (
                        <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">Loading reports...</TableCell></TableRow>
                      ) : filteredReports.length === 0 ? (
                        <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">No reports found.</TableCell></TableRow>
                      ) : (
                        filteredReports.map((report) => (
                          <TableRow key={report.report_id}>
                            <TableCell className="capitalize">{report.category}</TableCell>
                            <TableCell className="max-w-[360px]"><p className="text-sm line-clamp-2">{report.description}</p></TableCell>
                            <TableCell className="capitalize">{report.priority}</TableCell>
                            <TableCell><Badge variant={reportBadgeVariant(report.status)}>{report.status}</Badge></TableCell>
                            <TableCell>{formatDate(report.created_at)}</TableCell>
                            <TableCell>
                              <div className="flex flex-wrap gap-2">
                                <Button size="sm" variant="secondary" onClick={() => void handleReportStatus(report.report_id, "in_review")}>Review</Button>
                                <Button size="sm" variant="outline" onClick={() => void handleReportStatus(report.report_id, "resolved")}>Resolve</Button>
                                <Button size="sm" variant="ghost" onClick={() => void handleReportStatus(report.report_id, "dismissed")}>Dismiss</Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="feedback" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Feedback Inbox</CardTitle>
                <CardDescription>Track product feedback and close review loops.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="mb-4">
                  <Select value={feedbackFilter} onValueChange={(value: "all" | FeedbackStatus) => setFeedbackFilter(value)}>
                    <SelectTrigger className="w-[220px]"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Feedback Statuses</SelectItem>
                      <SelectItem value="open">Open</SelectItem>
                      <SelectItem value="reviewed">Reviewed</SelectItem>
                      <SelectItem value="dismissed">Dismissed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="rounded-lg border border-border overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>User</TableHead>
                        <TableHead>Rating</TableHead>
                        <TableHead>Comment</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {loadingFeedback ? (
                        <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">Loading feedback...</TableCell></TableRow>
                      ) : filteredFeedback.length === 0 ? (
                        <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">No feedback found.</TableCell></TableRow>
                      ) : (
                        filteredFeedback.map((entry) => (
                          <TableRow key={entry.feedback_id}>
                            <TableCell className="text-xs text-muted-foreground break-all">{entry.user_id}</TableCell>
                            <TableCell>
                              <div className="flex items-center gap-1">
                                <UserCheck className="h-4 w-4 text-accent" />
                                <span>{entry.rating ?? "-"}</span>
                              </div>
                            </TableCell>
                            <TableCell className="max-w-[360px]"><p className="text-sm line-clamp-2">{entry.comment}</p></TableCell>
                            <TableCell><Badge variant={feedbackBadgeVariant(entry.status)}>{entry.status}</Badge></TableCell>
                            <TableCell>{formatDate(entry.created_at)}</TableCell>
                            <TableCell>
                              <div className="flex flex-wrap gap-2">
                                <Button size="sm" variant="outline" onClick={() => void handleFeedbackStatus(entry.feedback_id, "reviewed")}>Mark Reviewed</Button>
                                <Button size="sm" variant="ghost" onClick={() => void handleFeedbackStatus(entry.feedback_id, "dismissed")}>Dismiss</Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="announcements" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Megaphone className="h-5 w-5" /> Compose Announcement</CardTitle>
                <CardDescription>Broadcast to all users or a targeted cohort.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid md:grid-cols-3 gap-3">
                  <div className="md:col-span-2 space-y-2">
                    <Label htmlFor="announcement-title">Title</Label>
                    <Input
                      id="announcement-title"
                      value={announcementTitle}
                      onChange={(event) => setAnnouncementTitle(event.target.value)}
                      placeholder="e.g. Scheduled maintenance window this Sunday"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="announcement-audience">Audience</Label>
                    <Select value={announcementAudience} onValueChange={(value: AnnouncementAudience) => setAnnouncementAudience(value)}>
                      <SelectTrigger id="announcement-audience"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All users</SelectItem>
                        <SelectItem value="patients">Patients only</SelectItem>
                        <SelectItem value="therapists">Therapists only</SelectItem>
                        <SelectItem value="inactive">Inactive users</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="announcement-body">Message</Label>
                  <Textarea
                    id="announcement-body"
                    value={announcementBody}
                    onChange={(event) => setAnnouncementBody(event.target.value)}
                    rows={4}
                    placeholder="Write a clear, supportive message. Markdown is not rendered."
                  />
                </div>
                <Button onClick={handleCreateAnnouncement} disabled={creatingAnnouncement}>
                  {creatingAnnouncement ? "Publishing…" : "Publish Announcement"}
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Published Announcements</CardTitle>
                <CardDescription>Deactivate to remove from user views.</CardDescription>
              </CardHeader>
              <CardContent>
                {loadingAnnouncements ? (
                  <p className="text-sm text-muted-foreground">Loading announcements...</p>
                ) : announcements.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No announcements yet.</p>
                ) : (
                  <div className="space-y-3">
                    {announcements.map((announcement) => (
                      <div key={announcement.announcement_id} className="p-4 rounded-lg border border-border bg-background/60">
                        <div className="flex items-start justify-between gap-3 mb-2">
                          <div>
                            <p className="font-semibold text-foreground">{announcement.title}</p>
                            <p className="text-xs text-muted-foreground">
                              {formatDate(announcement.created_at)} · Audience: <span className="capitalize">{announcement.audience}</span>
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant={announcement.active ? "default" : "outline"}>
                              {announcement.active ? "Active" : "Inactive"}
                            </Badge>
                            {announcement.active ? (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => setPendingAction({ kind: "announcement-deactivate", announcement })}
                              >
                                Deactivate
                              </Button>
                            ) : null}
                          </div>
                        </div>
                        <p className="text-sm text-foreground/90 whitespace-pre-wrap">{announcement.body}</p>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="logs" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><ScrollText className="h-5 w-5" /> Admin Audit Logs</CardTitle>
                <CardDescription>Immutable record of every admin action. Reason and actor are stored on each row.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="mb-4">
                  <Select value={logActionFilter} onValueChange={setLogActionFilter}>
                    <SelectTrigger className="w-[260px]"><SelectValue placeholder="Filter by action" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Actions</SelectItem>
                      {uniqueLogActions.map((action) => (
                        <SelectItem key={action} value={action}>{action}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="rounded-lg border border-border overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>When</TableHead>
                        <TableHead>Admin</TableHead>
                        <TableHead>Action</TableHead>
                        <TableHead>Target</TableHead>
                        <TableHead>Reason</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {loadingLogs ? (
                        <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">Loading audit logs...</TableCell></TableRow>
                      ) : logs.length === 0 ? (
                        <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">No audit entries yet.</TableCell></TableRow>
                      ) : (
                        logs.map((log) => (
                          <TableRow key={log.log_id}>
                            <TableCell className="text-xs text-muted-foreground whitespace-nowrap">{formatDate(log.created_at)}</TableCell>
                            <TableCell>
                              <p className="text-sm font-mono">{log.admin_id || "—"}</p>
                              <p className="text-xs text-muted-foreground break-all">{log.admin_user_id}</p>
                            </TableCell>
                            <TableCell><Badge variant="outline" className="font-mono text-xs">{log.action}</Badge></TableCell>
                            <TableCell>
                              <p className="text-xs text-muted-foreground break-all">{log.target_user_id || log.target_resource || "—"}</p>
                            </TableCell>
                            <TableCell className="max-w-[360px]">
                              <p className="text-sm line-clamp-3">{log.reason || "—"}</p>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        <div className="mt-8 grid md:grid-cols-3 gap-4 animate-fade-in-up delay-300">
          <Card>
            <CardContent className="p-5">
              <div className="flex items-center gap-3">
                <Shield className="h-5 w-5 text-primary" />
                <div>
                  <p className="text-sm font-medium">Role-based Access</p>
                  <p className="text-xs text-muted-foreground">Admin ID auto-assigned on promotion.</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-5">
              <div className="flex items-center gap-3">
                <Activity className="h-5 w-5 text-primary" />
                <div>
                  <p className="text-sm font-medium">Platform Monitoring</p>
                  <p className="text-xs text-muted-foreground">Watch weekly engagement and churn patterns.</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-5">
              <div className="flex items-center gap-3">
                <Ban className="h-5 w-5 text-secondary" />
                <div>
                  <p className="text-sm font-medium">Moderation Integrity</p>
                  <p className="text-xs text-muted-foreground">Every action is logged with reason and actor.</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>

      <ConfirmActionDialog
        open={pendingAction !== null}
        onOpenChange={(open) => { if (!open) setPendingAction(null); }}
        title={confirmDialogConfig?.title || ""}
        description={confirmDialogConfig?.description}
        targetLabel={confirmDialogConfig?.targetLabel}
        actionLabel={confirmDialogConfig?.actionLabel || "Confirm"}
        actionVariant={confirmDialogConfig?.actionVariant}
        onConfirm={handleConfirm}
      />

      <MobileNavigation />
    </div>
  );
}
