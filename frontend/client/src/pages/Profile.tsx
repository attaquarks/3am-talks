import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Navigation, MobileNavigation } from "@/components/Navigation";
import BackgroundDecor from '@/components/auth/BackgroundDecor';
import { useTheme } from "@/components/ThemeProvider";
import { User, Settings, Moon, Sun, Palette, Shield, Bell, Heart, TrendingUp, Calendar, Award, Download, Trash2, FileText } from "lucide-react";
import { useProfile } from "@/hooks/useProfile";
import { useUserStats } from "@/hooks/useUserStats";
import { useToast } from "@/hooks/use-toast";
import { useConversations } from "@/hooks/useConversations";
import { useMoodEntries } from "@/hooks/useMoodEntries";
import { useAuth } from "@/hooks/useAuth";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { useRef } from "react";
import jsPDF from "jspdf";
import { useNavigate } from "react-router-dom";

export default function Profile() {
  const { theme, setTheme } = useTheme();
  const { profile, updateProfile, loading: profileLoading } = useProfile();
  const { stats: userStats, loading: statsLoading, refreshStats } = useUserStats();
  const { toast } = useToast();
  const { signOut, user } = useAuth();
  const navigate = useNavigate();
  const [profileData, setProfileData] = useState({
    name: "",
    email: "",
    phone: "",
    joinDate: "",
    moodPreference: "neutral",
    emergencyContact: ""
  });
  const { conversations, refetch: refetchConversations } = useConversations();
  const { moodEntries, refetch: refetchMoodEntries } = useMoodEntries();
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [showDeleteAccountModal, setShowDeleteAccountModal] = useState(false);
  const [isDeletingAccount, setIsDeletingAccount] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const passwordInputRef = useRef<HTMLInputElement>(null);
  const [notificationEnabled, setNotificationEnabled] = useState(() => {
    return localStorage.getItem('ella-notification-enabled') === 'true';
  });
  const [notificationLoading, setNotificationLoading] = useState(false);
  const [showPrivacyModal, setShowPrivacyModal] = useState(false);
  const [deletingType, setDeletingType] = useState<'conversation' | 'mood' | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [privacyLoading, setPrivacyLoading] = useState(false);

  const apiRequest = async (endpoint: string, options: RequestInit = {}) => {
    const response = await fetch(endpoint, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ message: "Request failed" }));
      throw new Error(err.message || "Request failed");
    }
    return response;
  };

  useEffect(() => {
    if (profile) {
      setProfileData({
        name: profile.name,
        email: user?.email || "",
        phone: profile.phone || "",
        joinDate: new Date(profile.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long' }),
        moodPreference: profile.mood_preference,
        emergencyContact: profile.emergency_contact || ""
      });
    }
  }, [profile, user]);

  // Live polling for stats
  useEffect(() => {
    // Refresh stats immediately when component mounts
    refreshStats();
  }, [refreshStats]);

  const handleSaveChanges = async () => {
    setIsSaving(true);
    try {
      // Update profile data (name and mood preference)
      const trimmedPhone = profileData.phone.trim();
      if (trimmedPhone && !/^\+[1-9][0-9]{6,14}$/.test(trimmedPhone)) {
        toast({
          title: "Invalid phone",
          description: "Use E.164 format, e.g. +923001234567",
          variant: "destructive",
        });
        setIsSaving(false);
        return;
      }
      await updateProfile({
        name: profileData.name,
        mood_preference: profileData.moodPreference,
        emergency_contact: profileData.emergencyContact,
        phone: trimmedPhone,
      });

      // Email update requires dedicated backend auth endpoint (not implemented yet)
      if (user && profileData.email !== user.email) {
        await apiRequest("/api/account/email", {
          method: "PATCH",
          body: JSON.stringify({ new_email: profileData.email }),
        });
        toast({
          title: "Email Updated",
          description: "Your email address was updated successfully.",
        });
      }
    } catch (error) {
      console.error('Error saving changes:', error);
      toast({
        title: "Error",
        description: "Failed to save changes. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Helper to fetch all messages for all conversations
  const fetchAllMessages = async () => {
    const allMessages: Record<string, any[]> = {};
    for (const conv of conversations) {
      try {
        const response = await apiRequest(`/api/data/messages/${conv.id}`, { method: "GET" });
        const data = await response.json();
        allMessages[conv.id] = data || [];
      } catch (error) {
        console.error('Error fetching messages for conversation:', conv.id, error);
        allMessages[conv.id] = [];
      }
    }
    return allMessages;
  };

  const handleExportData = async () => {
    setIsExporting(true);
    try {
      await refetchConversations();
      await refetchMoodEntries();
      const allMessages = await fetchAllMessages();
      const currentUserId = user?.id || "user";

      const exportData = {
        profile: profileData,
        stats: userStats,
        conversations,
        messages: allMessages,
        moodEntries,
        exportedAt: new Date().toISOString(),
        userId: currentUserId,
      };

      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ella-export-${currentUserId}-${Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }, 100);

      toast({
        title: "Success",
        description: "Your data has been exported successfully.",
      });
    } catch (error) {
      console.error('Export error:', error);
      toast({
        title: "Error",
        description: "Failed to export data. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsExporting(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmNewPassword) {
      toast({ title: "Error", description: "New passwords do not match.", variant: "destructive" });
      return;
    }
    if (newPassword.length < 6) {
      toast({ title: "Error", description: "Password must be at least 6 characters long.", variant: "destructive" });
      return;
    }

    setIsChangingPassword(true);
    try {
      await apiRequest("/api/account/password", {
        method: "PATCH",
        body: JSON.stringify({
          old_password: oldPassword,
          new_password: newPassword,
        }),
      });
      toast({ title: "Success", description: "Password updated successfully." });
      setShowPasswordModal(false);
      setOldPassword("");
      setNewPassword("");
      setConfirmNewPassword("");
    } catch (err: any) {
      toast({
        title: "Error",
        description: err?.message || "Failed to update password.",
        variant: "destructive",
      });
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleDownloadPDF = async () => {
    setIsDownloading(true);
    try {
      await refetchConversations();
      const currentUserId = user?.id || "user";
      const allMessages: Record<string, any[]> = {};

      for (const conv of conversations) {
        const response = await apiRequest(`/api/data/messages/${conv.id}`, { method: "GET" });
        const data = await response.json();
        allMessages[conv.id] = data || [];
      }

      const doc = new jsPDF();
      doc.setFontSize(16);
      doc.text(`Conversation History for ${profileData.name || user?.email || 'User'}`, 10, 15);
      let y = 25;

      conversations.forEach((conv, idx) => {
        doc.setFontSize(14);
        doc.text(`Session ${idx + 1}: ${conv.title || 'Untitled'} (${new Date(conv.created_at).toLocaleString()})`, 10, y);
        y += 8;

        const messages = allMessages[conv.id] || [];
        messages.forEach((msg: any) => {
          doc.setFontSize(11);
          const who = msg.is_user ? 'You' : 'ELLA';
          const time = new Date(msg.created_at).toLocaleTimeString();
          const lines = doc.splitTextToSize(`${who} [${time}]: ${msg.content}`, 180);
          lines.forEach((line: string) => {
            if (y > 280) { doc.addPage(); y = 15; }
            doc.text(line, 12, y);
            y += 6;
          });
        });
        y += 8;
        if (y > 280) { doc.addPage(); y = 15; }
      });

      doc.save(`ella-conversation-history-${currentUserId}.pdf`);

      toast({
        title: "Success",
        description: "Conversation history downloaded successfully.",
      });
    } catch (error) {
      console.error('PDF download error:', error);
      toast({
        title: "Error",
        description: "Failed to download conversation history.",
        variant: "destructive",
      });
    } finally {
      setIsDownloading(false);
    }
  };

  const handleDeleteConversationHistory = async () => {
    if (confirm('Are you sure you want to delete all conversation history? This action cannot be undone.')) {
      try {
        for (const conv of conversations) {
          await apiRequest(`/api/data/conversations/${conv.id}`, { method: "DELETE" });
        }

        toast({
          title: "Success",
          description: "All conversation history has been deleted.",
        });

        await refetchConversations();
      } catch (error) {
        console.error('Error deleting conversations:', error);
        toast({
          title: "Error",
          description: "Failed to delete conversation history.",
          variant: "destructive",
        });
      }
    }
  };

  const handleDeleteAccount = async () => {
    setIsDeletingAccount(true);
    try {
      await apiRequest("/api/account", { method: "DELETE" });
      toast({
        title: "Account Deleted",
        description: "Your account and all associated data were deleted successfully.",
      });
      window.location.href = "/";
    } catch (error) {
      console.error('Error deleting account:', error);
      toast({
        title: "Error Deleting Account",
        description: error instanceof Error ? error.message : "Failed to delete account. Please try again or contact support.",
        variant: "destructive",
      });
    } finally {
      setIsDeletingAccount(false);
      setShowDeleteAccountModal(false);
    }
  };

  const handleConfigureNotifications = async () => {
    setNotificationLoading(true);
    if (!('Notification' in window)) {
      toast({ title: 'Error', description: 'Notifications are not supported in this browser.', variant: 'destructive' });
      setNotificationLoading(false);
      return;
    }
    if (Notification.permission === 'granted') {
      toggleNotification();
    } else if (Notification.permission !== 'denied') {
      const permission = await Notification.requestPermission();
      if (permission === 'granted') {
        toggleNotification();
      } else {
        toast({ title: 'Error', description: 'Notification permission denied.', variant: 'destructive' });
      }
    } else {
      toast({ title: 'Error', description: 'Notification permission denied.', variant: 'destructive' });
    }
    setNotificationLoading(false);
  };

  const toggleNotification = () => {
    const enabled = !notificationEnabled;
    setNotificationEnabled(enabled);
    localStorage.setItem('ella-notification-enabled', enabled ? 'true' : 'false');
    if (enabled) {
      toast({ title: 'Enabled', description: 'Daily check-in reminders enabled.' });
      scheduleDemoNotification();
    } else {
      toast({ title: 'Disabled', description: 'Daily check-in reminders disabled.' });
    }
  };

  // Demo: schedule a notification for the next day (in 10 seconds for demo)
  const scheduleDemoNotification = () => {
    setTimeout(() => {
      if (localStorage.getItem('ella-notification-enabled') === 'true') {
        new Notification('ELLA Check-in Reminder', {
          body: 'How are you feeling today? Don\'t forget your daily check-in!'
        });
      }
    }, 10000); // 10 seconds for demo
  };

  const handleDeleteConversation = async (id: string) => {
    setDeletingType('conversation');
    setDeletingId(id);
    setPrivacyLoading(true);
    try {
      await apiRequest(`/api/data/conversations/${id}`, { method: "DELETE" });
      toast({ title: 'Deleted', description: 'Conversation deleted.' });
      await refetchConversations();
    } catch (err) {
      toast({ title: 'Error', description: 'Failed to delete conversation.', variant: 'destructive' });
    } finally {
      setPrivacyLoading(false);
      setDeletingType(null);
      setDeletingId(null);
    }
  };

  const handleDeleteMoodEntry = async (id: string) => {
    setDeletingType('mood');
    setDeletingId(id);
    setPrivacyLoading(true);
    try {
      await apiRequest(`/api/data/mood_entries/${id}`, { method: "DELETE" });
      toast({ title: 'Deleted', description: 'Mood entry deleted.' });
      await refetchMoodEntries();
    } catch (err) {
      toast({ title: 'Error', description: 'Failed to delete mood entry.', variant: 'destructive' });
    } finally {
      setPrivacyLoading(false);
      setDeletingType(null);
      setDeletingId(null);
    }
  };

  // Helper: Calculate current streak from user stats
  function calculateCurrentStreak() {
    return userStats?.current_streak || 0;
  }

  // Helper: Calculate mood improvement from user stats
  function calculateMoodImprovement() {
    return userStats?.mood_improvement_percentage || 0;
  }

  const handleLogout = async () => {
    try {
      await signOut();
      toast({ title: "Logged out", description: "You have been successfully logged out." });
      // Navigate to landing page after logout
      navigate('/');
    } catch (error) {
      console.error('Logout error:', error);
      toast({ title: "Error", description: "Failed to log out. Please try again.", variant: "destructive" });
    }
  };

  // Dynamic stats
  const currentStreak = calculateCurrentStreak();
  const totalSessions = userStats?.total_sessions || 0;
  const totalMinutes = userStats?.total_minutes || 0;
  const moodImprovement = calculateMoodImprovement();

  const statsDisplay = [
    { label: "Current Streak", value: `${currentStreak} days`, icon: Award, color: "text-success" },
    { label: "Total Sessions", value: totalSessions.toString(), icon: Calendar, color: "text-primary" },
    { label: "Total Time", value: `${Math.floor(totalMinutes / 60)}h ${totalMinutes % 60}m`, icon: TrendingUp, color: "text-accent" },
    { label: "Mood Improvement", value: `${moodImprovement}%`, icon: Heart, color: "text-secondary" },
  ];

  return (
    <div className="min-h-screen relative flex flex-col bg-gradient-to-br from-primary/10 via-background to-secondary/10 selection:bg-primary/30 overflow-x-hidden">
      <BackgroundDecor />
      <Navigation />

      <main className="container mx-auto px-4 py-8 pb-20 md:pb-8">
        {/* Header */}
        <div className="mb-8 animate-fade-in-up">
          <h1 className="text-3xl font-bold text-foreground mb-2">
            Profile & Settings
          </h1>
          <p className="text-muted-foreground">
            Manage your account and customize your experience
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {/* Profile Info */}
          <div className="space-y-6">
            <Card className="animate-fade-in-up delay-100">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <User className="h-5 w-5 text-primary" />
                  <span>Profile Information</span>
                </CardTitle>
                <CardDescription>
                  Update your personal information
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-center mb-6">
                  <div className="w-20 h-20 bg-gradient-primary rounded-full flex items-center justify-center">
                    <span className="text-2xl font-bold text-white">
                      {profileData.name.split(" ").map(n => n[0]).join("")}
                    </span>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Full Name</label>
                  <Input
                    value={profileData.name}
                    onChange={(e) => setProfileData(prev => ({ ...prev, name: e.target.value }))}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Email</label>
                  <Input
                    type="email"
                    value={profileData.email}
                    onChange={(e) => setProfileData(prev => ({ ...prev, email: e.target.value }))}
                  />
                  {user && profileData.email !== user.email && (
                    <p className="text-xs text-muted-foreground">
                      Changing your email will require confirmation via email
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Your Phone</label>
                  <Input
                    type="tel"
                    placeholder="+923001234567"
                    value={profileData.phone}
                    onChange={(e) => setProfileData(prev => ({ ...prev, phone: e.target.value }))}
                  />
                  <p className="text-xs text-muted-foreground">
                    Used as your callback number in emergency safety alerts. E.164 format.
                  </p>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Emergency Contact</label>
                  <Input
                    type="tel"
                    placeholder="Enter emergency contact number"
                    value={profileData.emergencyContact}
                    onChange={(e) => setProfileData(prev => ({ ...prev, emergencyContact: e.target.value }))}
                  />
                  <p className="text-xs text-muted-foreground">
                    Legacy single contact. To configure WhatsApp alerts, use the Safety page.
                  </p>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">ELLA's Personality</label>
                  <select
                    value={profileData.moodPreference}
                    onChange={(e) => setProfileData(prev => ({ ...prev, moodPreference: e.target.value }))}
                    className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 shadow-soft-sm"
                  >
                    <option value="optimistic">Optimistic & Uplifting</option>
                    <option value="neutral">Balanced & Neutral</option>
                    <option value="gentle">Gentle & Caring</option>
                    <option value="motivational">Motivational & Encouraging</option>
                  </select>
                </div>

                <Button className="w-full mt-4" onClick={handleSaveChanges} disabled={profileLoading || isSaving}>
                  {profileLoading || isSaving ? "Saving..." : "Save Changes"}
                </Button>
              </CardContent>
            </Card>

            {/* Settings */}
            <Card className="animate-fade-in-up delay-200">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Settings className="h-5 w-5 text-primary" />
                  <span>Preferences</span>
                </CardTitle>
                <CardDescription>
                  Customize your app experience
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <Palette className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium text-foreground">Theme</p>
                      <p className="text-sm text-muted-foreground">Choose your preferred theme</p>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setTheme(theme === "light" ? "dark" : "light")}
                    className="flex items-center space-x-2"
                  >
                    {theme === "light" ? (
                      <>
                        <Moon className="h-4 w-4" />
                        <span>Dark</span>
                      </>
                    ) : (
                      <>
                        <Sun className="h-4 w-4" />
                        <span>Light</span>
                      </>
                    )}
                  </Button>
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <Bell className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium text-foreground">Notifications</p>
                      <p className="text-sm text-muted-foreground">Daily check-in reminders</p>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" onClick={handleConfigureNotifications} disabled={notificationLoading}>
                    {notificationEnabled ? 'Disable' : 'Configure'}
                  </Button>
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <Shield className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium text-foreground">Privacy</p>
                      <p className="text-sm text-muted-foreground">Manage your data and privacy</p>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => setShowPrivacyModal(true)}>
                    Review
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Stats & Progress */}
          <div className="space-y-6">
            <Card className="animate-fade-in-up delay-300">
              <CardHeader>
                <CardTitle>Your Journey Stats</CardTitle>
                <CardDescription>
                  Track your progress and achievements
                </CardDescription>
              </CardHeader>
              <CardContent>
                {statsLoading ? (
                  <div className="text-center py-4 text-muted-foreground">Loading stats...</div>
                ) : (
                  <div className="grid grid-cols-2 gap-4">
                    {statsDisplay.map((stat, index) => (
                      <div
                        key={index}
                        className="p-4 rounded-lg border border-border hover:bg-muted/50 transition-colors"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <stat.icon className={`h-5 w-5 ${stat.color}`} />
                          <span className={`text-lg font-bold ${stat.color}`}>
                            {stat.value}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground">{stat.label}</p>
                      </div>
                    ))}
                  </div>
                )}

                <div className="mt-6 p-4 bg-gradient-hero rounded-lg">
                  <h4 className="font-semibold text-foreground mb-2">Member since</h4>
                  <p className="text-sm text-muted-foreground">
                    You've been on your mental health journey with ELLA since {profileData.joinDate}
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Account Actions */}
            <Card className="animate-fade-in-up delay-400">
              <CardHeader>
                <CardTitle>Account</CardTitle>
                <CardDescription>
                  Manage your account settings
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Button
                  variant="outline"
                  className="w-full justify-start"
                  onClick={handleExportData}
                  disabled={isExporting}
                >
                  <FileText className="mr-2 h-4 w-4" />
                  {isExporting ? "Exporting..." : "Export My Data"}
                </Button>
                <Button
                  variant="outline"
                  className="w-full justify-start"
                  onClick={() => setShowPasswordModal(true)}
                >
                  <Shield className="mr-2 h-4 w-4" />
                  Change Password
                </Button>
                <Button
                  variant="outline"
                  className="w-full justify-start"
                  onClick={handleDownloadPDF}
                  disabled={isDownloading}
                >
                  <Download className="mr-2 h-4 w-4" />
                  {isDownloading ? "Downloading..." : "Download Conversation History"}
                </Button>
                <Button
                  variant="outline"
                  className="w-full justify-start"
                  onClick={handleDeleteConversationHistory}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete Conversation History
                </Button>
                <Button
                  variant="destructive"
                  className="w-full justify-start"
                  onClick={() => setShowDeleteAccountModal(true)}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete Account
                </Button>
              </CardContent>
            </Card>

            {/* Logout */}
            <Card className="animate-fade-in-up delay-500 border-2 border-destructive/20">
              <CardHeader>
                <CardTitle className="text-destructive">Session</CardTitle>
                <CardDescription>
                  Manage your current session
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button
                  variant="destructive"
                  className="w-full justify-start"
                  onClick={handleLogout}
                >
                  Logout
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>

      <MobileNavigation />

      {/* Password Change Modal */}
      <Dialog open={showPasswordModal} onOpenChange={setShowPasswordModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change Password</DialogTitle>
            <DialogDescription>Enter your old password and new password to update your account password.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleChangePassword} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Old Password</label>
              <Input
                type="password"
                value={oldPassword}
                onChange={e => setOldPassword(e.target.value)}
                ref={passwordInputRef}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">New Password</label>
              <Input
                type="password"
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Confirm New Password</label>
              <Input
                type="password"
                value={confirmNewPassword}
                onChange={e => setConfirmNewPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={isChangingPassword}>
              {isChangingPassword ? "Changing..." : "Change Password"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Account Modal */}
      <Dialog open={showDeleteAccountModal} onOpenChange={setShowDeleteAccountModal}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-destructive flex items-center gap-2">
              <Trash2 className="h-5 w-5" />
              Delete Account
            </DialogTitle>
            <DialogDescription>
              This action cannot be undone. This will permanently delete your account and remove all your data from our servers.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4">
              <h4 className="font-semibold text-destructive mb-2">⚠️ What will be COMPLETELY DELETED:</h4>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Your email address and password</li>
                <li>• All your therapy conversations</li>
                <li>• Your mood tracking history</li>
                <li>• Your progress statistics</li>
                <li>• Your profile information</li>
                <li>• Your account credentials</li>
                <li>• Your entire user account</li>
              </ul>
            </div>
            <p className="text-sm text-muted-foreground">
              This action is irreversible. Once deleted, your email will be completely removed and you CANNOT log in with it again.
            </p>
            <DialogFooter className="gap-2">
              <Button
                variant="outline"
                onClick={() => setShowDeleteAccountModal(false)}
                disabled={isDeletingAccount}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDeleteAccount}
                disabled={isDeletingAccount}
                className="min-w-[120px]"
              >
                {isDeletingAccount ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Deleting...
                  </>
                ) : (
                  "Delete Account"
                )}
              </Button>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>

      {/* Privacy Modal */}
      <Dialog open={showPrivacyModal} onOpenChange={setShowPrivacyModal}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Privacy & Data Management</DialogTitle>
            <DialogDescription>View and manage your data. You can delete specific conversations or mood entries. <a href="/privacy-policy" className="text-primary underline ml-1" target="_blank" rel="noopener noreferrer">Privacy Policy</a></DialogDescription>
          </DialogHeader>
          <div className="max-h-[60vh] overflow-y-auto space-y-6">
            <div>
              <h4 className="font-semibold mb-2">Profile</h4>
              <pre className="bg-muted p-2 rounded text-xs overflow-x-auto">{JSON.stringify(profileData, null, 2)}</pre>
            </div>
            <div>
              <h4 className="font-semibold mb-2">Journey Stats</h4>
              <pre className="bg-muted p-2 rounded text-xs overflow-x-auto">{JSON.stringify(userStats, null, 2)}</pre>
            </div>
            <div>
              <h4 className="font-semibold mb-2">Mood Entries</h4>
              {moodEntries.length === 0 ? <p className="text-muted-foreground">No mood entries.</p> : (
                <ul className="space-y-2">
                  {moodEntries.map(entry => (
                    <li key={entry.id} className="flex items-center justify-between bg-muted p-2 rounded">
                      <span className="text-xs">{entry.date}: {entry.mood} {entry.note && `- ${entry.note}`}</span>
                      <Button size="sm" variant="destructive" disabled={privacyLoading && deletingType === 'mood' && deletingId === entry.id} onClick={() => handleDeleteMoodEntry(entry.id)}>
                        Delete
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <h4 className="font-semibold mb-2">Conversations</h4>
              {conversations.length === 0 ? <p className="text-muted-foreground">No conversations.</p> : (
                <ul className="space-y-2">
                  {conversations.map(conv => (
                    <li key={conv.id} className="flex items-center justify-between bg-muted p-2 rounded">
                      <span className="text-xs">{conv.title || 'Untitled'} ({new Date(conv.created_at).toLocaleDateString()})</span>
                      <Button size="sm" variant="destructive" disabled={privacyLoading && deletingType === 'conversation' && deletingId === conv.id} onClick={() => handleDeleteConversation(conv.id)}>
                        Delete
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}