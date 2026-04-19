import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Navigation, MobileNavigation } from "@/components/Navigation";
import BackgroundDecor from '@/components/auth/BackgroundDecor';
import PersonalityTraits from '@/components/PersonalityTraits';
import { MessageCircle, BookOpen, TrendingUp, Calendar as CalendarIcon, Smile, Meh, Frown, Brain } from "lucide-react";
import { Link } from "react-router-dom";
import { useProfile } from "@/hooks/useProfile";
import { useMoodEntries } from "@/hooks/useMoodEntries";
import { useUserStats } from "@/hooks/useUserStats";
// import { supabase } from "@/integrations/supabase/client"; // Removed

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Slider } from "@/components/ui/slider";
import { useToast } from "@/hooks/use-toast";
import { Calendar } from "@/components/ui/calendar";
import HomeworkCard from "@/components/patient/HomeworkCard";

// Add/extend MoodEntry type for prompt and prompt_answer
type MoodEntry = {
  id: string;
  user_id: string;
  date: string;
  mood: string;
  note?: string | null;
  prompt?: string | null;
  prompt_answer?: string | null;
  created_at?: string;
  updated_at?: string;
};

const WELCOME_GREETINGS = [
  "Welcome back",
  "Good to see you again",
  "Hey there, glad you're here",
  "You made it back",
  "Always nice to see you",
  "Look who's here",
  "Welcome home",
  "Hi there, sunshine",
  "The light was on for you",
  "Back for a bit? Perfect",
  "You showed up — that counts",
  "Warm welcome back",
  "Pull up a chair",
  "You, again — lovely",
  "Glad you dropped in",
];

const WELCOME_SUBLINES = [
  "Ready to continue your mental health journey?",
  "What's on your mind today?",
  "Take a breath. You've got this.",
  "No pressure — go at your own pace.",
  "A small step today still counts.",
  "ELLA's here whenever you're ready.",
  "How's your heart doing today?",
  "Let's make today a little lighter.",
  "Small check-ins, big difference.",
  "You're exactly where you need to be.",
];

function pickRandom<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [greeting] = useState(() => pickRandom(WELCOME_GREETINGS));
  const [subline] = useState(() => pickRandom(WELCOME_SUBLINES));
  const { profile, loading: profileLoading } = useProfile();
  // using createMoodEntry from hook
  const { moodEntries, loading: moodLoading, createMoodEntry } = useMoodEntries();
  const { stats, loading: statsLoading, refreshStats } = useUserStats();
  const { toast } = useToast();
  const [showCheckinModal, setShowCheckinModal] = useState(false);
  const [showMoodJournal, setShowMoodJournal] = useState(false);
  const [showFullCalendar, setShowFullCalendar] = useState(false);
  const [moodValue, setMoodValue] = useState(2);
  const [note, setNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState(null);
  const moodEmojis = [
    { value: 0, emoji: "😭", label: "Very Sad" },
    { value: 1, emoji: "😢", label: "Sad" },
    { value: 2, emoji: "😐", label: "Neutral" },
    { value: 3, emoji: "🙂", label: "Happy" },
    { value: 4, emoji: "😄", label: "Very Happy" },
  ];
  const moodPrompts = [
    "It seems like you're having a really tough day. What happened?",
    "Sorry you're feeling sad. Would you like to share what's making you feel this way?",
    "Feeling neutral today. Is there anything bothering you or on your mind?",
    "That's great! What made you feel happy today?",
    "Awesome! What made you smile or feel very happy today?"
  ];
  const todayPrompt = moodPrompts[moodValue];
  const [promptAnswer, setPromptAnswer] = useState("");
  const [selectedDay, setSelectedDay] = useState<Date>(new Date());
  const [showMCQModal, setShowMCQModal] = useState(false);
  const [mcqAnswers, setMcqAnswers] = useState<number[]>([]);
  const [mcqResult, setMcqResult] = useState<null | { mood: string; value: number; label: string; emoji: string }>(null);
  const mcqQuestions = [
    {
      q: "How much energy do you have right now?",
      options: ["None", "Low", "Neutral", "Good", "Very high"]
    },
    {
      q: "How optimistic do you feel about today?",
      options: ["Not at all", "A little", "Neutral", "Optimistic", "Very optimistic"]
    },
    {
      q: "How much did you enjoy your recent activities?",
      options: ["Not at all", "A little", "Neutral", "Enjoyed", "Loved them"]
    },
    {
      q: "How connected do you feel to others?",
      options: ["Very isolated", "Somewhat isolated", "Neutral", "Connected", "Very connected"]
    },
    {
      q: "How much stress are you feeling?",
      options: ["Extreme", "High", "Moderate", "Low", "None"]
    },
    {
      q: "How well did you sleep last night?",
      options: ["Very poorly", "Poorly", "Okay", "Well", "Very well"]
    }
  ];
  const mcqMoodMap = [
    { value: 0, mood: "very_sad", label: "Very Sad", emoji: "😭" },
    { value: 1, mood: "sad", label: "Sad", emoji: "😢" },
    { value: 2, mood: "neutral", label: "Neutral", emoji: "😐" },
    { value: 3, mood: "happy", label: "Happy", emoji: "🙂" },
    { value: 4, mood: "very_happy", label: "Very Happy", emoji: "😄" }
  ];
  const handleMCQSubmit = () => {
    const avg = Math.round(mcqAnswers.reduce((a, b) => a + b, 0) / mcqAnswers.length);
    setMcqResult(mcqMoodMap[avg]);
  };
  const handleAcceptMCQMood = () => {
    setMoodValue(mcqResult?.value || 2);
    setShowMCQModal(false);
    setShowCheckinModal(true);
    setMcqAnswers([]);
    setMcqResult(null);
  };

  useEffect(() => {
    // Remove old authentication check - now handled by AuthWrapper
    // The AuthWrapper component handles all authentication and redirects
  }, []);

  const getMoodIcon = (mood: string) => {
    switch (mood) {
      case "happy":
        return <Smile className="h-4 w-4 text-success" />;
      case "neutral":
        return <Meh className="h-4 w-4 text-warning" />;
      case "sad":
        return <Frown className="h-4 w-4 text-destructive" />;
      default:
        return <Meh className="h-4 w-4 text-muted-foreground" />;
    }
  };

  // Helper: Get this week's mood entries
  const getThisWeeksEntries = () => {
    const now = new Date();
    const weekAgo = new Date(now);
    weekAgo.setDate(now.getDate() - 6);
    return moodEntries.filter(e => {
      const d = new Date(e.date);
      return d >= weekAgo && d <= now;
    });
  };

  // Helper: Calculate mood improvement for this week
  const calculateMoodImprovement = (entries: any[]) => {
    if (entries.length < 2) return 0;
    const scores = entries.map((e: any) => {
      switch (e.mood) {
        case "very_sad": return 0;
        case "sad": return 1;
        case "neutral": return 2;
        case "happy": return 3;
        case "very_happy": return 4;
        default: return 2;
      }
    });
    const first = scores[scores.length - 1];
    const last = scores[0];
    if (first === 0) return 0;
    return Math.round(((last - first) / Math.max(1, first)) * 100);
  };

  const handleCheckinSubmit = async () => {
    // Prevent empty logs
    if (!note.trim() && !promptAnswer.trim()) {
      toast({
        title: "Please reflect",
        description: "Please write something about your day or answer the reflection prompt before submitting.",
        variant: "destructive",
        duration: 5000
      });
      return;
    }
    setIsSubmitting(true);
    const moodMap = ["very_sad", "sad", "neutral", "happy", "very_happy"];
    const mood = moodMap[moodValue];
    const todayStr = new Date().toISOString().split('T')[0];

    try {
      const result = await createMoodEntry({
        date: todayStr,
        mood,
        note: note || null,
        prompt: todayPrompt || null,
        prompt_answer: promptAnswer || null
      });

      if (result) {
        toast({
          title: "Check-in complete!",
          description: `You checked in as ${moodEmojis[moodValue].label}.`
        });
        setShowCheckinModal(false);
        setMoodValue(2);
        setNote("");
        setPromptAnswer("");
        refreshStats();
      }
    } catch (err) {
      // Error handled by hook logic actually, but just in case
      console.error('Mood entry error:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Calendar grid for the month
  const getMonthDays = () => {
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    return Array.from({ length: daysInMonth }, (_, i) => new Date(year, month, i + 1));
  };
  const monthDays = getMonthDays();
  const entryByDate = Object.fromEntries(moodEntries.map(e => [e.date, e]));

  // Helper: Check if user has already logged mood today
  const hasLoggedToday = !!entryByDate[new Date().toISOString().split('T')[0]];

  // Helper: Calculate current streak
  function calculateCurrentStreak(entries: MoodEntry[]) {
    if (!entries.length) return 0;
    const dates = entries.map(e => e.date).sort();
    let streak = 0;
    let prev = null;
    let today = new Date();
    let foundToday = false;
    for (let i = dates.length - 1; i >= 0; i--) {
      const entryDate = new Date(dates[i]);
      if (!foundToday) {
        if (entryDate.toDateString() === today.toDateString()) {
          streak = 1;
          foundToday = true;
        } else {
          break;
        }
        prev = entryDate;
        continue;
      }
      if (prev) {
        const diff = (prev.getTime() - entryDate.getTime()) / (1000 * 60 * 60 * 24);
        if (diff === 1) {
          streak++;
          prev = entryDate;
        } else {
          break;
        }
      }
    }
    return streak;
  }
  // Helper: Calculate consistency (days logged this month)
  function calculateConsistency(entries: MoodEntry[]) {
    const days = new Set(entries.map(e => e.date));
    return days.size;
  }
  // Helper: Calculate improvement (this week)
  function calculateImprovement(entries: MoodEntry[]) {
    const weekEntries = entries.filter(e => {
      const d = new Date(e.date);
      const now = new Date();
      const weekAgo = new Date(now);
      weekAgo.setDate(now.getDate() - 6);
      return d >= weekAgo && d <= now;
    });
    if (weekEntries.length < 2) return 0;
    const scores = weekEntries.map(e => {
      switch (e.mood) {
        case "very_sad": return 0;
        case "sad": return 1;
        case "neutral": return 2;
        case "happy": return 3;
        case "very_happy": return 4;
        default: return 2;
      }
    });
    const first = scores[scores.length - 1];
    const last = scores[0];
    if (first === 0) return 0;
    return Math.round(((last - first) / Math.max(1, first)) * 100);
  }
  const currentStreak = calculateCurrentStreak(moodEntries);
  const consistency = calculateConsistency(moodEntries);
  const improvement = calculateImprovement(moodEntries);
  // Badges
  const badges = [
    currentStreak >= 7 && { icon: "🔥", label: "7-day Streak!" },
    consistency >= 20 && { icon: "🏅", label: "Consistent Logger" },
    improvement >= 20 && { icon: "🚀", label: "Mood Improved!" },
  ].filter(Boolean);

  return (
    <div className="min-h-screen relative bg-gradient-to-br from-primary/10 via-background to-secondary/10 selection:bg-primary/30">
      <BackgroundDecor />
      <Navigation />
      <main className="relative z-10 container mx-auto px-4 sm:px-6 lg:px-10 py-6 pb-24 max-w-7xl">
        {/* Welcome */}
        <div className="text-center mb-6 animate-fade-in-up">
          <h1 className="text-2xl md:text-3xl font-light tracking-tight text-foreground mb-1">
            {greeting}, {profileLoading ? '...' : (profile?.name || 'User')} 👋
          </h1>
          <p className="text-sm text-muted-foreground">{subline}</p>
        </div>

        {/* Live stats strip */}
        {!statsLoading && stats && (
          <div className="grid grid-cols-3 gap-4 md:gap-6 mb-6 max-w-3xl mx-auto animate-fade-in-up delay-75">
            <div className="rounded-2xl border border-border bg-background/60 backdrop-blur px-5 py-4 text-center">
              <div className="text-2xl md:text-3xl font-semibold text-primary leading-none">🌟 {stats.current_streak}</div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground mt-2">Streak</div>
            </div>
            <div className="rounded-2xl border border-border bg-background/60 backdrop-blur px-5 py-4 text-center">
              <div className="text-2xl md:text-3xl font-semibold text-primary leading-none">📊 {stats.mood_improvement_percentage}%</div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground mt-2">Improvement</div>
            </div>
            <div className="rounded-2xl border border-border bg-background/60 backdrop-blur px-5 py-4 text-center">
              <div className="text-2xl md:text-3xl font-semibold text-primary leading-none">💝 {stats.total_sessions}</div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground mt-2">Sessions</div>
            </div>
          </div>
        )}

        {/* Quick Actions */}
        <div className="grid sm:grid-cols-3 gap-3 mb-6 animate-fade-in-up delay-100">
          <Link to="/therapist" className="block">
            <Card className="cursor-pointer group hover:shadow-glow transition-all duration-300 h-full">
              <CardContent className="p-5">
                <div className="flex items-center space-x-4">
                  <div className="w-11 h-11 bg-gradient-primary rounded-xl flex items-center justify-center group-hover:animate-float shrink-0">
                    <MessageCircle className="h-5 w-5 text-white" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="font-semibold text-foreground text-sm">Start Conversation</h3>
                    <p className="text-xs text-muted-foreground">Talk to ELLA now</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </Link>

          <Card className="cursor-pointer group hover:shadow-glow transition-all duration-300 h-full" onClick={() => setShowMoodJournal(true)}>
            <CardContent className="p-5">
              <div className="flex items-center space-x-4">
                <div className="w-11 h-11 bg-secondary rounded-xl flex items-center justify-center group-hover:animate-float shrink-0">
                  <BookOpen className="h-5 w-5 text-white" />
                </div>
                <div className="min-w-0">
                  <h3 className="font-semibold text-foreground text-sm">Mood Journal</h3>
                  <p className="text-xs text-muted-foreground">Log your feelings</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Link to="/history" className="block">
            <Card className="cursor-pointer group hover:shadow-glow transition-all duration-300 h-full">
              <CardContent className="p-5">
                <div className="flex items-center space-x-4">
                  <div className="w-11 h-11 bg-accent rounded-xl flex items-center justify-center group-hover:animate-float shrink-0">
                    <TrendingUp className="h-5 w-5 text-white" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="font-semibold text-foreground text-sm">Insights</h3>
                    <p className="text-xs text-muted-foreground">View your progress</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </Link>
        </div>

        {/* Main content: 2-up on md+, stacked on mobile */}
        <div className="grid md:grid-cols-2 gap-5 mb-6 animate-fade-in-up delay-200">
          {/* Mood — check-in + recent entries combined */}
          <Card className="h-full flex flex-col">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <CalendarIcon className="h-4 w-4 text-primary" />
                <span>Your Mood</span>
              </CardTitle>
              <CardDescription className="text-xs">
                {hasLoggedToday ? "Logged for today — nice work." : "A 30-second check-in, then your recent entries."}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col gap-4">
              {/* Check-in CTA */}
              <div className="flex items-center gap-4 p-4 rounded-2xl bg-gradient-to-br from-primary/5 to-secondary/5 border border-border/60">
                <div className="w-12 h-12 bg-gradient-hero rounded-full flex items-center justify-center shrink-0 animate-pulse-soft">
                  <MessageCircle className="h-5 w-5 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">
                    {hasLoggedToday ? "See you tomorrow" : "How are you feeling today?"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {hasLoggedToday ? "Come back for tomorrow's log." : "Quick mood + reflection."}
                  </p>
                </div>
                <Button
                  variant="hero"
                  size="sm"
                  onClick={() => setShowCheckinModal(true)}
                  disabled={hasLoggedToday}
                  className="shrink-0"
                >
                  {hasLoggedToday ? "Done" : "Check-in"}
                </Button>
              </div>

              {/* Recent entries */}
              <div className="flex-1 flex flex-col min-h-0">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Recent entries</p>
                  {moodEntries.length > 0 && (
                    <span className="text-[10px] text-muted-foreground">{moodEntries.length} total</span>
                  )}
                </div>
                <div className="space-y-2 flex-1">
                  {moodLoading ? (
                    <div className="text-center py-4 text-muted-foreground text-sm">Loading...</div>
                  ) : moodEntries.length === 0 ? (
                    <div className="text-center py-6 text-muted-foreground text-sm">
                      No entries yet — your first check-in starts the streak.
                    </div>
                  ) : (
                    moodEntries.slice(0, 4).map((entry) => (
                      <div
                        key={entry.id}
                        className="flex items-center gap-3 p-2.5 rounded-xl border border-border hover:bg-muted/40 transition-colors"
                      >
                        {getMoodIcon(entry.mood)}
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium text-foreground">
                            {new Date(entry.date).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}
                          </p>
                          <p className="text-xs text-muted-foreground truncate">{entry.note || 'No note'}</p>
                        </div>
                      </div>
                    ))
                  )}
                </div>
                <Button variant="outline" size="sm" className="w-full mt-3" onClick={() => setShowFullCalendar(true)}>
                  <CalendarIcon className="mr-2 h-3 w-3" />
                  View full calendar
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Personality Traits */}
          <Card className="h-full flex flex-col">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Brain className="h-4 w-4 text-primary" />
                <span>Personality Profile</span>
              </CardTitle>
              <CardDescription className="text-xs">Big Five traits from your ELLA sessions</CardDescription>
            </CardHeader>
            <CardContent className="flex-1">
              <PersonalityTraits profile={profile} loading={profileLoading} />
            </CardContent>
          </Card>
        </div>

        {/* Homework — full width, integrated */}
        <div className="animate-fade-in-up delay-300">
          <HomeworkCard />
        </div>
      </main>

      <Dialog open={showMoodJournal} onOpenChange={setShowMoodJournal}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-2xl font-bold text-center">Mood Journal</DialogTitle>
            <DialogDescription className="text-center">
              Track your moods, write notes, and reflect with daily prompts. Your journey to better mental health starts here.
            </DialogDescription>
          </DialogHeader>

          <div className="py-6">
            {/* Quick Mood Assessment */}
            <div className="mb-8 p-6 bg-background/60 backdrop-blur-sm rounded-xl border border-border/50 shadow-sm hover:shadow-md transition-all duration-300">
              <div className="text-center mb-4">
                <div className="text-3xl mb-3 animate-pulse">🤔</div>
                <div className="font-semibold text-lg mb-2 bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
                  Not sure how you feel?
                </div>
                <p className="text-sm text-muted-foreground mb-4">
                  Take our quick assessment to help identify your current mood
                </p>
                <Button
                  variant="outline"
                  className="w-full max-w-md bg-primary/10 hover:bg-primary/20 border-primary/30 hover:border-primary/50 transition-all duration-200"
                  onClick={() => setShowMCQModal(true)}
                >
                  <span className="mr-2">🧠</span>
                  Take Mood Assessment
                </Button>
              </div>
            </div>

            {/* Calendar Section */}
            <div className="mb-8">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-xl font-semibold">
                    {selectedDay.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Track your daily mood patterns
                  </p>
                </div>
                <div className="text-sm bg-primary/10 text-primary px-3 py-1 rounded-full">
                  Today: {new Date().toLocaleDateString()}
                </div>
              </div>

              <div className="bg-transparent rounded-xl border border-border/50 p-6">
                <Calendar
                  mode="single"
                  selected={selectedDay}
                  onSelect={(date) => date && setSelectedDay(date)}
                  modifiers={{
                    today: new Date(),
                    hasEntry: (date) => !!entryByDate[date.toISOString().split('T')[0]],
                  }}
                  modifiersClassNames={{
                    today: "bg-primary text-primary-foreground rounded-full font-semibold",
                    hasEntry: "bg-accent/20 border-accent text-accent-foreground font-semibold",
                  }}
                  disabled={(date) => date > new Date()}
                  components={{
                    Day: ({ date, ...props }) => {
                      const dateStr = date.toISOString().split('T')[0];
                      const entry = entryByDate[dateStr];
                      const isToday = date.toDateString() === new Date().toDateString();

                      return (
                        <div
                          {...props}
                          className={`flex flex-col items-center justify-center w-full h-full relative p-2 transition-all duration-200 ${isToday ? 'bg-primary text-primary-foreground rounded-full font-semibold' : ''
                            }`}
                        >
                          {entry && (
                            <span className="text-lg absolute -top-1 animate-bounce">
                              {moodEmojis.find(m => m.value === ["very_sad", "sad", "neutral", "happy", "very_happy"].indexOf(entry.mood))?.emoji}
                            </span>
                          )}
                          <span className={`text-sm mt-2 ${isToday ? 'text-primary-foreground' : 'text-foreground'}`}>
                            {date.getDate()}
                          </span>
                        </div>
                      );
                    },
                  }}
                  className="w-full bg-transparent"
                />
              </div>
            </div>

            {/* Progress & Badges */}
            <div className="mb-8">
              <h3 className="text-xl font-semibold mb-4">Your Progress</h3>

              {/* Badges */}
              <div className="mb-6">
                <h4 className="font-medium mb-3">Achievements</h4>
                <div className="flex flex-wrap gap-3">
                  {badges.length > 0 ? badges.map((b, i) => (
                    <div key={i} className="inline-flex items-center px-4 py-2 rounded-full bg-gradient-to-r from-yellow-100 to-orange-100 border border-yellow-200 text-yellow-800 font-semibold text-sm shadow-sm animate-pulse">
                      <span className="mr-2 text-xl">{b && typeof b === 'object' && 'icon' in b ? b.icon : ''}</span>
                      {b && typeof b === 'object' && 'label' in b ? b.label : ''}
                    </div>
                  )) : (
                    <div className="text-center py-4 text-muted-foreground">
                      <div className="text-2xl mb-2">🎯</div>
                      <p className="text-sm">Keep logging your moods to earn badges!</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Streak Progress */}
              <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl p-6 border border-green-100">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-semibold text-green-800">Current Streak</h4>
                  <span className="text-2xl font-bold text-green-600">{currentStreak} days</span>
                </div>
                <div className="w-full bg-green-200 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-green-400 to-emerald-500 h-3 rounded-full transition-all duration-500 ease-out"
                    style={{ width: `${Math.min((currentStreak / 7) * 100, 100)}%` }}
                  />
                </div>
                <div className="text-xs text-green-600 mt-2">
                  {currentStreak}/7 days to next milestone
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="mb-8">
              <h3 className="text-xl font-semibold mb-4">Quick Actions</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Button
                  variant="default"
                  className="h-16 text-lg font-semibold bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white"
                  onClick={() => {
                    setSelectedDay(new Date());
                    setShowCheckinModal(true);
                  }}
                  disabled={selectedDay.toDateString() !== new Date().toDateString()}
                >
                  <span className="mr-2">📝</span>
                  Log Today's Mood
                </Button>

                <Button
                  variant="outline"
                  className="h-16 text-lg font-semibold"
                  onClick={() => setShowMCQModal(true)}
                >
                  <span className="mr-2">🧠</span>
                  Mood Assessment
                </Button>
              </div>
            </div>

            {/* Selected Day Entry */}
            {selectedDay && entryByDate[selectedDay.toISOString().split('T')[0]] && (
              <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-200">
                <h3 className="text-xl font-semibold mb-4">Entry for {selectedDay.toLocaleDateString()}</h3>
                {(() => {
                  const entry = entryByDate[selectedDay.toISOString().split('T')[0]] as MoodEntry;
                  return (
                    <div className="space-y-4">
                      {/* Mood Display */}
                      <div className="flex items-center space-x-4 p-4 bg-white rounded-lg border border-blue-100">
                        <span className="text-4xl">
                          {moodEmojis.find(m => m.value === ["very_sad", "sad", "neutral", "happy", "very_happy"].indexOf(entry.mood))?.emoji}
                        </span>
                        <div>
                          <div className="font-semibold text-lg capitalize">
                            {entry.mood.replace('_', ' ')}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {selectedDay.toLocaleDateString()}
                          </div>
                        </div>
                      </div>

                      {/* Note */}
                      {entry.note && (
                        <div className="p-4 bg-white rounded-lg border border-blue-100">
                          <div className="font-medium mb-2">📝 Your Note</div>
                          <p className="text-sm text-gray-700">{entry.note}</p>
                        </div>
                      )}

                      {/* Prompt & Reflection */}
                      {entry.prompt && (
                        <div className="p-4 bg-white rounded-lg border border-blue-100">
                          <div className="font-medium mb-2">💭 Reflection Prompt</div>
                          <p className="text-sm text-gray-600 mb-3 italic">"{entry.prompt}"</p>
                          {entry.prompt_answer && (
                            <>
                              <div className="font-medium mb-2">✨ Your Reflection</div>
                              <p className="text-sm text-gray-700">{entry.prompt_answer}</p>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })()}
              </div>
            )}

            {/* Tips */}
            <div className="mt-8 p-6 bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl border border-purple-100">
              <h3 className="font-semibold mb-3 text-purple-800">💡 Tips for Better Mood Tracking</h3>
              <ul className="space-y-2 text-sm text-purple-700">
                <li>• Log your mood at the same time each day for consistency</li>
                <li>• Be honest about how you're feeling - there's no right or wrong</li>
                <li>• Use the reflection prompts to gain deeper insights</li>
                <li>• Review your patterns weekly to spot trends</li>
                <li>• Celebrate your progress, no matter how small</li>
              </ul>
            </div>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={showCheckinModal} onOpenChange={setShowCheckinModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Log Mood for Today</DialogTitle>
            <DialogDescription>How are you feeling today? Slide to select your mood, write a note, and reflect.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col items-center space-y-6 py-4">
            <Slider
              min={0}
              max={4}
              step={1}
              value={[moodValue]}
              onValueChange={([v]) => setMoodValue(v)}
              className="w-full max-w-xs"
            />
            <div className="flex justify-between w-full max-w-xs mt-2">
              {moodEmojis.map((m, i) => (
                <span key={i} className={moodValue === m.value ? "text-2xl" : "text-xl opacity-60"} title={m.label}>{m.emoji}</span>
              ))}
            </div>
            {hasLoggedToday ? (
              <div className="w-full max-w-xs text-center text-muted-foreground text-base font-medium py-8">
                You can only log your mood once a day. Come back tomorrow and keep up the good work!
              </div>
            ) : (
              <>
                <textarea
                  className="w-full max-w-xs rounded-lg border border-border bg-background p-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                  rows={3}
                  placeholder="Write a short note about your day..."
                  value={note}
                  onChange={e => setNote(e.target.value)}
                />
                <div className="w-full max-w-xs">
                  <div className="font-medium mb-1">Reflection Prompt</div>
                  <div className="text-muted-foreground mb-2 transition-all duration-200">{todayPrompt}</div>
                  <textarea
                    className="w-full rounded-lg border border-border bg-background p-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                    rows={2}
                    placeholder="Your reflection..."
                    value={promptAnswer}
                    onChange={e => setPromptAnswer(e.target.value)}
                  />
                </div>
              </>
            )}
          </div>
          <DialogFooter>
            <Button onClick={handleCheckinSubmit} disabled={isSubmitting || hasLoggedToday} className="w-full" variant="hero">
              {isSubmitting ? "Logging..." : "Submit"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={showMCQModal} onOpenChange={setShowMCQModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Quick Mood MCQ Test</DialogTitle>
            <DialogDescription>Answer these questions to help us estimate your mood.</DialogDescription>
          </DialogHeader>
          <div className="space-y-6 py-2">
            {mcqResult ? (
              <div className="text-center">
                <div className="text-4xl mb-2">{mcqResult.emoji}</div>
                <div className="font-bold text-lg mb-2">We think your mood is: {mcqResult.label}</div>
                <Button variant="hero" className="w-full" onClick={handleAcceptMCQMood}>
                  Accept and Log Mood
                </Button>
                <Button variant="outline" className="w-full mt-2" onClick={() => setMcqResult(null)}>
                  Go Back
                </Button>
              </div>
            ) : (
              <form
                onSubmit={e => {
                  e.preventDefault();
                  handleMCQSubmit();
                }}
                className="space-y-4"
              >
                {mcqQuestions.map((q, i) => (
                  <div key={i} className="mb-2">
                    <div className="font-medium mb-1">{q.q}</div>
                    <div className="flex gap-2 flex-wrap">
                      {q.options.map((opt, j) => (
                        <label key={j} className={`cursor-pointer px-3 py-1 rounded-full border ${mcqAnswers[i] === j ? 'bg-primary text-primary-foreground border-primary' : 'bg-muted border-border'}`}>
                          <input
                            type="radio"
                            name={`mcq-${i}`}
                            value={j}
                            checked={mcqAnswers[i] === j}
                            onChange={() => {
                              const newAns = [...mcqAnswers];
                              newAns[i] = j;
                              setMcqAnswers(newAns);
                            }}
                            className="hidden"
                          />
                          {opt}
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
                <Button type="submit" className="w-full" variant="hero" disabled={mcqAnswers.length !== mcqQuestions.length}>
                  Analyze Mood
                </Button>
              </form>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Full Calendar Modal */}
      <Dialog open={showFullCalendar} onOpenChange={setShowFullCalendar}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-2xl font-bold text-center">Full Mood Calendar</DialogTitle>
            <DialogDescription className="text-center">
              View your complete mood journey and track your emotional patterns over time.
            </DialogDescription>
          </DialogHeader>

          <div className="py-6">
            {/* Calendar Navigation */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-xl font-semibold">
                  {selectedDay.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
                </h3>
                <p className="text-sm text-muted-foreground">
                  Click on any date to view your mood entry
                </p>
              </div>
              <div className="text-sm bg-primary/10 text-primary px-3 py-1 rounded-full">
                {moodEntries.length} entries this month
              </div>
            </div>

            {/* Full Calendar */}
            <div className="bg-transparent rounded-xl border border-border/50 p-6 mb-6">
              <Calendar
                mode="single"
                selected={selectedDay}
                onSelect={(date) => date && setSelectedDay(date)}
                modifiers={{
                  today: new Date(),
                  hasEntry: (date) => !!entryByDate[date.toISOString().split('T')[0]],
                }}
                modifiersClassNames={{
                  today: "bg-primary text-primary-foreground rounded-full font-semibold",
                  hasEntry: "bg-accent/20 border-accent text-accent-foreground font-semibold",
                }}
                disabled={(date) => date > new Date()}
                components={{
                  Day: ({ date, ...props }) => {
                    const dateStr = date.toISOString().split('T')[0];
                    const entry = entryByDate[dateStr];
                    const isToday = date.toDateString() === new Date().toDateString();

                    return (
                      <div
                        {...props}
                        className={`flex flex-col items-center justify-center w-full h-full relative p-2 transition-all duration-200 cursor-pointer hover:bg-muted/50 ${isToday ? 'bg-primary text-primary-foreground rounded-full font-semibold' : ''
                          }`}
                      >
                        {entry && (
                          <span className="text-lg absolute -top-1 animate-bounce">
                            {moodEmojis.find(m => m.value === ["very_sad", "sad", "neutral", "happy", "very_happy"].indexOf(entry.mood))?.emoji}
                          </span>
                        )}
                        <span className={`text-sm mt-2 ${isToday ? 'text-primary-foreground' : 'text-foreground'}`}>
                          {date.getDate()}
                        </span>
                      </div>
                    );
                  },
                }}
                className="w-full bg-transparent"
              />
            </div>

            {/* Selected Day Details */}
            {selectedDay && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold">
                    {selectedDay.toLocaleDateString(undefined, {
                      weekday: 'long',
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    })}
                  </h3>
                  {entryByDate[selectedDay.toISOString().split('T')[0]] && (
                    <span className="text-sm bg-green-100 text-green-800 px-2 py-1 rounded-full">
                      ✓ Logged
                    </span>
                  )}
                </div>

                {entryByDate[selectedDay.toISOString().split('T')[0]] ? (
                  <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-200">
                    {(() => {
                      const entry = entryByDate[selectedDay.toISOString().split('T')[0]] as MoodEntry;
                      return (
                        <div className="space-y-4">
                          {/* Mood Display */}
                          <div className="flex items-center space-x-4 p-4 bg-white rounded-lg border border-blue-100">
                            <span className="text-4xl">
                              {moodEmojis.find(m => m.value === ["very_sad", "sad", "neutral", "happy", "very_happy"].indexOf(entry.mood))?.emoji}
                            </span>
                            <div>
                              <div className="font-semibold text-lg capitalize">
                                {entry.mood.replace('_', ' ')}
                              </div>
                              <div className="text-sm text-muted-foreground">
                                {selectedDay.toLocaleDateString()}
                              </div>
                            </div>
                          </div>

                          {/* Note */}
                          {entry.note && (
                            <div className="p-4 bg-white rounded-lg border border-blue-100">
                              <div className="font-medium mb-2">📝 Your Note</div>
                              <p className="text-sm text-gray-700">{entry.note}</p>
                            </div>
                          )}

                          {/* Prompt & Reflection */}
                          {entry.prompt && (
                            <div className="p-4 bg-white rounded-lg border border-blue-100">
                              <div className="font-medium mb-2">💭 Reflection Prompt</div>
                              <p className="text-sm text-gray-600 mb-3 italic">"{entry.prompt}"</p>
                              {entry.prompt_answer && (
                                <>
                                  <div className="font-medium mb-2">✨ Your Reflection</div>
                                  <p className="text-sm text-gray-700">{entry.prompt_answer}</p>
                                </>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                ) : (
                  <div className="bg-gradient-to-r from-gray-50 to-gray-100 rounded-xl p-6 border border-gray-200 text-center">
                    <div className="text-4xl mb-3">📅</div>
                    <h4 className="font-semibold text-gray-700 mb-2">No Entry for This Day</h4>
                    <p className="text-sm text-gray-600 mb-4">
                      {selectedDay.toDateString() === new Date().toDateString()
                        ? "Log your mood for today to start tracking your journey!"
                        : "You didn't log your mood on this day."
                      }
                    </p>
                    {selectedDay.toDateString() === new Date().toDateString() && (
                      <Button
                        onClick={() => {
                          setShowFullCalendar(false);
                          setShowCheckinModal(true);
                        }}
                        className="bg-primary hover:bg-primary/90"
                      >
                        Log Today's Mood
                      </Button>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Monthly Stats */}
            <div className="mt-8 p-6 bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl border border-purple-100">
              <h3 className="font-semibold mb-4 text-purple-800">📊 Monthly Overview</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="text-center p-4 bg-white rounded-lg border border-purple-200">
                  <div className="text-2xl font-bold text-purple-600">{consistency}</div>
                  <div className="text-sm text-purple-700">Days Logged</div>
                </div>
                <div className="text-center p-4 bg-white rounded-lg border border-purple-200">
                  <div className="text-2xl font-bold text-purple-600">{currentStreak}</div>
                  <div className="text-sm text-purple-700">Current Streak</div>
                </div>
                <div className="text-center p-4 bg-white rounded-lg border border-purple-200">
                  <div className="text-2xl font-bold text-purple-600">{improvement}%</div>
                  <div className="text-sm text-purple-700">Mood Improvement</div>
                </div>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <MobileNavigation />
    </div>
  );
}