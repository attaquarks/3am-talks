import { useEffect, useState } from "react";
import { Navigation, MobileNavigation } from "@/components/Navigation";
import BackgroundDecor from "@/components/auth/BackgroundDecor";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { therapistFetchJson } from "@/lib/therapistFetch";
import { TherapistProfile as TherapistProfileType } from "@/types/auth";
import { Loader2, Save, Stethoscope } from "lucide-react";

export default function TherapistProfile() {
    const { toast } = useToast();
    const [profile, setProfile] = useState<TherapistProfileType | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    const [form, setForm] = useState({
        display_name: "",
        title: "",
        license_number: "",
        license_jurisdiction: "",
        specializations: "",
        modalities: "",
        languages: "",
        years_experience: "",
        bio: "",
        pronouns: "",
        photo_url: "",
        timezone: "",
        max_caseload: "",
        accepting_patients: true,
    });

    useEffect(() => {
        const run = async () => {
            try {
                const data = await therapistFetchJson<{ profile: TherapistProfileType }>("/api/therapist/me");
                const p = data.profile || {} as TherapistProfileType;
                setProfile(p);
                setForm({
                    display_name: p.display_name ?? "",
                    title: p.title ?? "",
                    license_number: p.license_number ?? "",
                    license_jurisdiction: p.license_jurisdiction ?? "",
                    specializations: (p.specializations ?? []).join(", "),
                    modalities: (p.modalities ?? []).join(", "),
                    languages: (p.languages ?? []).join(", "),
                    years_experience: p.years_experience?.toString() ?? "",
                    bio: p.bio ?? "",
                    pronouns: p.pronouns ?? "",
                    photo_url: p.photo_url ?? "",
                    timezone: p.timezone ?? "",
                    max_caseload: p.max_caseload?.toString() ?? "",
                    accepting_patients: p.accepting_patients ?? true,
                });
            } catch (err: any) {
                toast({ title: "Couldn't load profile", description: err.message, variant: "destructive" });
            } finally {
                setLoading(false);
            }
        };
        run();
    }, [toast]);

    const handleSave = async () => {
        setSaving(true);
        try {
            const payload: Record<string, unknown> = {
                display_name: form.display_name || null,
                title: form.title || null,
                license_number: form.license_number || null,
                license_jurisdiction: form.license_jurisdiction || null,
                specializations: form.specializations.split(",").map((s) => s.trim()).filter(Boolean),
                modalities: form.modalities.split(",").map((s) => s.trim()).filter(Boolean),
                languages: form.languages.split(",").map((s) => s.trim()).filter(Boolean),
                years_experience: form.years_experience ? parseInt(form.years_experience, 10) : null,
                bio: form.bio || null,
                pronouns: form.pronouns || null,
                photo_url: form.photo_url || null,
                timezone: form.timezone || null,
                max_caseload: form.max_caseload ? parseInt(form.max_caseload, 10) : null,
                accepting_patients: form.accepting_patients,
            };
            await therapistFetchJson("/api/therapist/me", {
                method: "PATCH",
                body: JSON.stringify(payload),
            });
            toast({ title: "Profile saved" });
        } catch (err: any) {
            toast({ title: "Save failed", description: err.message, variant: "destructive" });
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-primary/5 via-background to-secondary/10 relative">
            <BackgroundDecor />
            <Navigation />

            <main className="relative z-10 container mx-auto px-4 sm:px-6 lg:px-8 py-12 max-w-4xl space-y-6">
                <div className="flex items-center gap-4">
                    <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center">
                        <Stethoscope className="h-7 w-7 text-primary" />
                    </div>
                    <div>
                        <h1 className="text-3xl font-light tracking-tight">Clinical Profile</h1>
                        <p className="text-sm text-muted-foreground">
                            This is what patients see before linking with you.
                        </p>
                    </div>
                </div>

                {loading ? (
                    <div className="flex justify-center py-20">
                        <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    </div>
                ) : (
                    <>
                        <Card className="rounded-3xl">
                            <CardHeader>
                                <div className="flex items-center justify-between">
                                    <div>
                                        <CardTitle>Public details</CardTitle>
                                        <CardDescription>Shown in the patient-facing therapist directory.</CardDescription>
                                    </div>
                                    {profile?.license_verified_at && (
                                        <Badge variant="secondary">License verified</Badge>
                                    )}
                                </div>
                            </CardHeader>
                            <CardContent className="grid md:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>Display name</Label>
                                    <Input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} placeholder="Dr. Jane Smith" />
                                </div>
                                <div className="space-y-2">
                                    <Label>Title</Label>
                                    <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Licensed Clinical Psychologist" />
                                </div>
                                <div className="space-y-2">
                                    <Label>Pronouns</Label>
                                    <Input value={form.pronouns} onChange={(e) => setForm({ ...form, pronouns: e.target.value })} placeholder="she/her" />
                                </div>
                                <div className="space-y-2">
                                    <Label>Years of experience</Label>
                                    <Input type="number" value={form.years_experience} onChange={(e) => setForm({ ...form, years_experience: e.target.value })} placeholder="10" />
                                </div>
                                <div className="space-y-2 md:col-span-2">
                                    <Label>Photo URL</Label>
                                    <Input value={form.photo_url} onChange={(e) => setForm({ ...form, photo_url: e.target.value })} placeholder="https://..." />
                                </div>
                                <div className="space-y-2 md:col-span-2">
                                    <Label>Bio</Label>
                                    <Textarea rows={4} value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} placeholder="A short bio for patients..." />
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="rounded-3xl">
                            <CardHeader>
                                <CardTitle>Clinical expertise</CardTitle>
                                <CardDescription>Comma-separated values.</CardDescription>
                            </CardHeader>
                            <CardContent className="grid md:grid-cols-2 gap-4">
                                <div className="space-y-2 md:col-span-2">
                                    <Label>Specializations</Label>
                                    <Input value={form.specializations} onChange={(e) => setForm({ ...form, specializations: e.target.value })} placeholder="anxiety, trauma, depression" />
                                </div>
                                <div className="space-y-2 md:col-span-2">
                                    <Label>Modalities</Label>
                                    <Input value={form.modalities} onChange={(e) => setForm({ ...form, modalities: e.target.value })} placeholder="CBT, DBT, ACT" />
                                </div>
                                <div className="space-y-2">
                                    <Label>Languages</Label>
                                    <Input value={form.languages} onChange={(e) => setForm({ ...form, languages: e.target.value })} placeholder="English, Urdu" />
                                </div>
                                <div className="space-y-2">
                                    <Label>Timezone</Label>
                                    <Input value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} placeholder="America/Los_Angeles" />
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="rounded-3xl">
                            <CardHeader>
                                <CardTitle>License</CardTitle>
                                <CardDescription>Verified by the Ella team.</CardDescription>
                            </CardHeader>
                            <CardContent className="grid md:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>License number</Label>
                                    <Input value={form.license_number} onChange={(e) => setForm({ ...form, license_number: e.target.value })} />
                                </div>
                                <div className="space-y-2">
                                    <Label>Jurisdiction</Label>
                                    <Input value={form.license_jurisdiction} onChange={(e) => setForm({ ...form, license_jurisdiction: e.target.value })} />
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="rounded-3xl">
                            <CardHeader>
                                <CardTitle>Caseload settings</CardTitle>
                                <CardDescription>Control your capacity.</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="flex items-center justify-between gap-4 rounded-2xl border border-border p-4">
                                    <div>
                                        <p className="font-medium text-sm">Accepting new patients</p>
                                        <p className="text-xs text-muted-foreground">Turn off to pause incoming link requests.</p>
                                    </div>
                                    <Switch
                                        checked={form.accepting_patients}
                                        onCheckedChange={(v) => setForm({ ...form, accepting_patients: v })}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>Max caseload</Label>
                                    <Input type="number" value={form.max_caseload} onChange={(e) => setForm({ ...form, max_caseload: e.target.value })} placeholder="25" />
                                </div>
                            </CardContent>
                        </Card>

                        <div className="flex justify-end">
                            <Button onClick={handleSave} disabled={saving} size="lg" className="rounded-xl">
                                {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                                Save profile
                            </Button>
                        </div>
                    </>
                )}
            </main>

            <MobileNavigation />
        </div>
    );
}
