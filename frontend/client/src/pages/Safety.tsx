import { useCallback, useEffect, useState } from "react";
import { Navigation, MobileNavigation } from "@/components/Navigation";
import BackgroundDecor from "@/components/auth/BackgroundDecor";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
    Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { useProfile } from "@/hooks/useProfile";
import {
    crisisApi, CrisisSettings, EmergencyContact, NotificationChannel,
    E164_REGEX, DEFAULT_CONSENT_TEXT, CrisisEvent,
} from "@/lib/crisisApi";
import {
    ShieldAlert, PhoneCall, Plus, Trash2, Pencil, BellRing, Loader2, AlertTriangle, History,
} from "lucide-react";

const RELATIONSHIPS = [
    "mother", "father", "sister", "brother", "spouse", "partner",
    "best friend", "friend", "guardian", "cousin", "other",
];

export default function Safety() {
    const { toast } = useToast();
    const { profile } = useProfile();

    const [settings, setSettings] = useState<CrisisSettings | null>(null);
    const [contacts, setContacts] = useState<EmergencyContact[]>([]);
    const [events, setEvents] = useState<CrisisEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [savingSettings, setSavingSettings] = useState(false);
    const [testing, setTesting] = useState(false);

    // Form state for settings
    const [enabled, setEnabled] = useState(false);
    const [locationConsent, setLocationConsent] = useState(false);
    const [countdown, setCountdown] = useState(30);
    const [country, setCountry] = useState("PK");
    const [userPhone, setUserPhone] = useState("");

    // Add/edit contact dialog
    const [contactDialog, setContactDialog] = useState<{ open: boolean; editing?: EmergencyContact }>({ open: false });
    const [cName, setCName] = useState("");
    const [cPhone, setCPhone] = useState("");
    const [cRel, setCRel] = useState("friend");
    const [cChannel, setCChannel] = useState<NotificationChannel>("whatsapp");
    const [savingContact, setSavingContact] = useState(false);

    const reload = useCallback(async () => {
        setLoading(true);
        try {
            const [s, c, e] = await Promise.all([
                crisisApi.getSettings(),
                crisisApi.listContacts(),
                crisisApi.listEvents(20),
            ]);
            setSettings(s);
            setContacts(c.contacts || []);
            setEvents(e.events || []);
            setEnabled(!!s.emergency_alerts_enabled);
            setLocationConsent(!!s.location_sharing_consent);
            setCountdown(s.countdown_seconds || 30);
            setCountry(s.country_code || "PK");
            // Prefer saved safety phone, otherwise fall back to profile.phone
            setUserPhone(s.user_phone || profile?.phone || "");
        } catch (err) {
            toast({ title: "Failed to load", description: String(err), variant: "destructive" });
        } finally {
            setLoading(false);
        }
    }, [toast, profile?.phone]);

    useEffect(() => { reload(); }, [reload]);

    const saveSettings = async () => {
        if (userPhone && !E164_REGEX.test(userPhone.trim())) {
            toast({ title: "Invalid phone", description: "Use E.164 format, e.g. +923001234567", variant: "destructive" });
            return;
        }
        setSavingSettings(true);
        try {
            const updated = await crisisApi.updateSettings({
                emergency_alerts_enabled: enabled,
                location_sharing_consent: locationConsent,
                consent_text_shown: DEFAULT_CONSENT_TEXT,
                countdown_seconds: countdown,
                country_code: country,
                user_phone: userPhone.trim() || null,
            });
            setSettings(updated);
            toast({ title: "Saved", description: "Safety settings updated." });
        } catch (err) {
            toast({ title: "Save failed", description: String(err), variant: "destructive" });
        } finally {
            setSavingSettings(false);
        }
    };

    const openAddContact = () => {
        setCName(""); setCPhone(""); setCRel("friend"); setCChannel("whatsapp");
        setContactDialog({ open: true });
    };
    const openEditContact = (c: EmergencyContact) => {
        setCName(c.contact_name); setCPhone(c.contact_phone);
        setCRel(c.relationship || "friend"); setCChannel(c.notification_channel);
        setContactDialog({ open: true, editing: c });
    };
    const closeContactDialog = () => setContactDialog({ open: false });

    const submitContact = async () => {
        if (!cName.trim()) {
            toast({ title: "Name required", variant: "destructive" }); return;
        }
        if (!E164_REGEX.test(cPhone.trim())) {
            toast({ title: "Invalid phone", description: "Use E.164 format, e.g. +923344117908", variant: "destructive" }); return;
        }
        setSavingContact(true);
        try {
            if (contactDialog.editing) {
                await crisisApi.updateContact(contactDialog.editing.id, {
                    contact_name: cName.trim(),
                    contact_phone: cPhone.trim(),
                    relationship: cRel,
                    notification_channel: cChannel,
                });
            } else {
                await crisisApi.addContact({
                    contact_name: cName.trim(),
                    contact_phone: cPhone.trim(),
                    relationship: cRel,
                    notification_channel: cChannel,
                });
            }
            toast({ title: "Contact saved" });
            closeContactDialog();
            await reload();
        } catch (err) {
            toast({ title: "Save failed", description: String(err), variant: "destructive" });
        } finally {
            setSavingContact(false);
        }
    };

    const removeContact = async (c: EmergencyContact) => {
        if (!confirm(`Remove ${c.contact_name}? They will no longer receive safety alerts.`)) return;
        try {
            await crisisApi.deleteContact(c.id);
            await reload();
            toast({ title: "Removed" });
        } catch (err) {
            toast({ title: "Failed", description: String(err), variant: "destructive" });
        }
    };

    const sendTestAlert = async () => {
        if (contacts.length === 0) {
            toast({ title: "No contacts", description: "Add an emergency contact first.", variant: "destructive" });
            return;
        }
        if (!confirm(`This will send a TEST WhatsApp/SMS to all ${contacts.length} active contact(s). Continue?`)) return;
        setTesting(true);
        try {
            const r = await crisisApi.testAlert();
            toast({
                title: "Test alert sent",
                description: `Notified ${r.contacts_notified} contact(s).`,
            });
            await reload();
        } catch (err) {
            toast({ title: "Test failed", description: String(err), variant: "destructive" });
        } finally {
            setTesting(false);
        }
    };

    return (
        <div className="min-h-screen relative">
            <BackgroundDecor />
            <Navigation />
            <MobileNavigation />

            <main className="container mx-auto max-w-4xl px-4 pt-24 pb-32 space-y-6">
                <div className="flex items-center gap-3">
                    <ShieldAlert className="w-7 h-7 text-rose-500" />
                    <div>
                        <h1 className="text-2xl font-semibold">Safety & Emergency Alerts</h1>
                        <p className="text-sm text-muted-foreground">
                            Configure who Ella should reach out to if it detects you may be in immediate danger.
                        </p>
                    </div>
                </div>

                {loading && (
                    <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin" /></div>
                )}

                {!loading && (
                    <>
                        {/* Consent + Settings */}
                        <Card>
                            <CardHeader>
                                <CardTitle>Crisis safety settings</CardTitle>
                                <CardDescription>
                                    These controls govern when and how emergency contacts are notified. Off by default.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="flex items-center justify-between gap-4">
                                    <div>
                                        <Label className="text-base">Emergency alerts</Label>
                                        <p className="text-xs text-muted-foreground">
                                            Allow Ella to notify your contacts during a confirmed crisis.
                                        </p>
                                    </div>
                                    <Switch checked={enabled} onCheckedChange={setEnabled} />
                                </div>

                                <div className="flex items-center justify-between gap-4">
                                    <div>
                                        <Label className="text-base">Share my location</Label>
                                        <p className="text-xs text-muted-foreground">
                                            Includes a Google Maps link in the alert when location is available.
                                        </p>
                                    </div>
                                    <Switch checked={locationConsent} onCheckedChange={setLocationConsent} />
                                </div>

                                <div>
                                    <Label className="text-base">Cancellation window: {countdown}s</Label>
                                    <p className="text-xs text-muted-foreground mb-2">
                                        How long you have to cancel before alerts go out (10–120 seconds).
                                    </p>
                                    <Slider
                                        min={10} max={120} step={5}
                                        value={[countdown]}
                                        onValueChange={(v) => setCountdown(v[0])}
                                    />
                                </div>

                                <div className="grid sm:grid-cols-2 gap-4">
                                    <div>
                                        <Label htmlFor="country">Country (helplines)</Label>
                                        <Select value={country} onValueChange={setCountry}>
                                            <SelectTrigger id="country"><SelectValue /></SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="PK">Pakistan</SelectItem>
                                                <SelectItem value="US">United States</SelectItem>
                                                <SelectItem value="GB">United Kingdom</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div>
                                        <Label htmlFor="userPhone">Your callback number</Label>
                                        <Input
                                            id="userPhone"
                                            placeholder="+923001234567"
                                            value={userPhone}
                                            onChange={(e) => setUserPhone(e.target.value)}
                                        />
                                        <p className="text-xs text-muted-foreground mt-1">
                                            Included in the alert so contacts know which number to call. Defaults to your profile phone.
                                        </p>
                                    </div>
                                </div>

                                <div className="rounded-md border border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-900/40 p-3 text-xs text-amber-900 dark:text-amber-200 flex gap-2">
                                    <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                                    <span>
                                        By turning on emergency alerts you consent to: <em>{DEFAULT_CONSENT_TEXT}</em>
                                    </span>
                                </div>

                                <Button onClick={saveSettings} disabled={savingSettings}>
                                    {savingSettings ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                                    Save settings
                                </Button>
                            </CardContent>
                        </Card>

                        {/* Contacts */}
                        <Card>
                            <CardHeader className="flex flex-row items-start justify-between gap-4">
                                <div>
                                    <CardTitle>Emergency contacts</CardTitle>
                                    <CardDescription>
                                        WhatsApp sandbox requires each contact to send <code>join &lt;code&gt;</code> to the
                                        Twilio sandbox number first.
                                    </CardDescription>
                                </div>
                                <Button size="sm" onClick={openAddContact}>
                                    <Plus className="w-4 h-4 mr-1" /> Add contact
                                </Button>
                            </CardHeader>
                            <CardContent className="space-y-2">
                                {contacts.length === 0 && (
                                    <p className="text-sm text-muted-foreground py-4 text-center">
                                        No contacts yet. Add at least one to enable alerts.
                                    </p>
                                )}
                                {contacts.map((c) => (
                                    <div key={c.id} className="flex items-center justify-between gap-3 rounded-md border p-3">
                                        <div className="min-w-0">
                                            <div className="font-medium truncate">
                                                {c.contact_name}{" "}
                                                {c.relationship && (
                                                    <span className="text-xs text-muted-foreground font-normal">
                                                        ({c.relationship})
                                                    </span>
                                                )}
                                            </div>
                                            <div className="text-xs text-muted-foreground">
                                                {c.contact_phone} · <Badge variant="secondary" className="ml-1">{c.notification_channel}</Badge>
                                            </div>
                                        </div>
                                        <div className="flex gap-1">
                                            <Button size="icon" variant="ghost" onClick={() => openEditContact(c)}>
                                                <Pencil className="w-4 h-4" />
                                            </Button>
                                            <Button size="icon" variant="ghost" onClick={() => removeContact(c)}>
                                                <Trash2 className="w-4 h-4 text-rose-500" />
                                            </Button>
                                        </div>
                                    </div>
                                ))}

                                <div className="pt-2">
                                    <Button variant="outline" onClick={sendTestAlert} disabled={testing || contacts.length === 0}>
                                        {testing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <BellRing className="w-4 h-4 mr-2" />}
                                        Send test alert
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Events */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <History className="w-5 h-5" /> Recent crisis events
                                </CardTitle>
                                <CardDescription>Detected events from the last 20 sessions.</CardDescription>
                            </CardHeader>
                            <CardContent>
                                {events.length === 0 ? (
                                    <p className="text-sm text-muted-foreground py-4 text-center">No events yet.</p>
                                ) : (
                                    <div className="space-y-2">
                                        {events.map((e) => (
                                            <div key={e.event_id} className="flex items-start justify-between gap-3 text-sm rounded-md border p-2">
                                                <div>
                                                    <div className="font-medium capitalize">
                                                        {e.severity}{" "}
                                                        <span className="text-xs text-muted-foreground font-normal">
                                                            · {e.intervention_type}
                                                        </span>
                                                    </div>
                                                    <div className="text-xs text-muted-foreground">
                                                        {new Date(e.created_at).toLocaleString()}
                                                        {e.contacts_notified.length > 0 && (
                                                            <> · notified {e.contacts_notified.join(", ")}</>
                                                        )}
                                                    </div>
                                                </div>
                                                {e.emergency_alerts_sent ? (
                                                    <Badge variant="destructive">Alert sent</Badge>
                                                ) : (
                                                    <Badge variant="secondary">No alert</Badge>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </>
                )}
            </main>

            <Dialog open={contactDialog.open} onOpenChange={(o) => !o && closeContactDialog()}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{contactDialog.editing ? "Edit contact" : "Add emergency contact"}</DialogTitle>
                        <DialogDescription>
                            They will receive a WhatsApp/SMS alert during a confirmed crisis.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-3">
                        <div>
                            <Label htmlFor="cName">Name</Label>
                            <Input id="cName" value={cName} onChange={(e) => setCName(e.target.value)} />
                        </div>
                        <div>
                            <Label htmlFor="cPhone">Phone (E.164)</Label>
                            <Input id="cPhone" placeholder="+923001234567" value={cPhone} onChange={(e) => setCPhone(e.target.value)} />
                        </div>
                        <div>
                            <Label htmlFor="cRel">Relationship</Label>
                            <Select value={cRel} onValueChange={setCRel}>
                                <SelectTrigger id="cRel"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    {RELATIONSHIPS.map((r) => (
                                        <SelectItem key={r} value={r} className="capitalize">{r}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <Label htmlFor="cCh">Notification channel</Label>
                            <Select value={cChannel} onValueChange={(v) => setCChannel(v as NotificationChannel)}>
                                <SelectTrigger id="cCh"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="whatsapp">WhatsApp</SelectItem>
                                    <SelectItem value="sms">SMS</SelectItem>
                                    <SelectItem value="both">Both</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="ghost" onClick={closeContactDialog}>Cancel</Button>
                        <Button onClick={submitContact} disabled={savingContact}>
                            {savingContact ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <PhoneCall className="w-4 h-4 mr-2" />}
                            Save
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
