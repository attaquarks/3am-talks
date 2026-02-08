import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Navigation, MobileNavigation } from "@/components/Navigation";
import BackgroundDecor from '@/components/auth/BackgroundDecor';
import { Search, Filter, Calendar, MessageCircle, Smile, Meh, Frown } from "lucide-react";
import { cn } from "@/lib/utils";
import { useConversations } from "@/hooks/useConversations";
import { useUserStats } from "@/hooks/useUserStats";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";

interface ConversationEntry {
  id: string;
  date: Date;
  duration: string;
  mood: "happy" | "neutral" | "sad";
  summary: string;
  tags: string[];
  messages?: any[];
}

export default function History() {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedFilter, setSelectedFilter] = useState("all");
  const [selectedConversation, setSelectedConversation] = useState<any>(null);
  const { conversations, loading: conversationsLoading } = useConversations();
  const { stats, loading: statsLoading } = useUserStats();
  const [conversationDetails, setConversationDetails] = useState<Record<string, any>>({});

  // Generate real summaries and format durations
  const generateRealSummary = (conversation: any, messages: any[]): string => {
    if (!messages || messages.length === 0) return "New conversation started";

    const userMessages = messages.filter(m => m.is_user).map(m => m.content);
    if (userMessages.length === 0) return "Conversation started";

    const allText = userMessages.join(' ').toLowerCase();

    // Simple keyword-based summary
    const topics = [];
    if (allText.includes('work') || allText.includes('job') || allText.includes('career')) topics.push('work');
    if (allText.includes('relationship') || allText.includes('partner') || allText.includes('family')) topics.push('relationships');
    if (allText.includes('anxiety') || allText.includes('stress') || allText.includes('worry')) topics.push('anxiety');
    if (allText.includes('depression') || allText.includes('sad') || allText.includes('down')) topics.push('depression');
    if (allText.includes('sleep') || allText.includes('tired') || allText.includes('rest')) topics.push('sleep');
    if (allText.includes('health') || allText.includes('exercise') || allText.includes('fitness')) topics.push('health');
    if (allText.includes('school') || allText.includes('study') || allText.includes('exam')) topics.push('education');
    if (allText.includes('money') || allText.includes('financial') || allText.includes('budget')) topics.push('finances');

    if (topics.length > 0) {
      return `Discussed ${topics.slice(0, 2).join(', ')}`;
    }

    // Fallback to first few words of first message
    const firstMessage = userMessages[0];
    if (firstMessage.length > 25) {
      return firstMessage.substring(0, 25) + '...';
    }
    return firstMessage;
  };

  const formatTimeAgo = (date: Date): string => {
    const now = new Date();
    const diffInMs = now.getTime() - date.getTime();
    const diffInMinutes = Math.floor(diffInMs / (1000 * 60));
    const diffInHours = Math.floor(diffInMs / (1000 * 60 * 60));
    const diffInDays = Math.floor(diffInMs / (1000 * 60 * 60 * 24));

    if (diffInMinutes < 1) return "Just now";
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
    if (diffInHours < 24) return `${diffInHours}h ago`;
    if (diffInDays < 7) return `${diffInDays}d ago`;
    return date.toLocaleDateString();
  };

  const formatDuration = (minutes: number): string => {
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };

  // Load conversation details (messages) for summaries
  useEffect(() => {
    const loadConversationDetails = async () => {
      const details: Record<string, any> = {};

      for (const conv of conversations) {
        try {
          const { data: messages } = await supabase
            .from('messages')
            .select('*')
            .eq('conversation_id', conv.id)
            .order('created_at', { ascending: true });

          details[conv.id] = messages || [];
        } catch (error) {
          console.error('Error loading messages for conversation:', conv.id, error);
          details[conv.id] = [];
        }
      }

      setConversationDetails(details);
    };

    if (conversations.length > 0) {
      loadConversationDetails();
    }
  }, [conversations]);

  // Convert conversations to match the expected format with real data
  const conversationHistory = conversations.map(conv => {
    const messages = conversationDetails[conv.id] || [];
    const realSummary = generateRealSummary(conv, messages);
    const timeAgo = formatTimeAgo(new Date(conv.created_at));
    const duration = formatDuration(conv.duration_minutes || 0);

    return {
      id: conv.id,
      date: new Date(conv.created_at),
      duration: duration,
      timeAgo: timeAgo,
      mood: conv.mood as "happy" | "neutral" | "sad" | null,
      summary: realSummary,
      tags: conv.tags || [],
      messages: messages
    };
  });

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

  const getMoodColor = (mood: string) => {
    switch (mood) {
      case "happy":
        return "border-l-success";
      case "neutral":
        return "border-l-warning";
      case "sad":
        return "border-l-destructive";
      default:
        return "border-l-muted-foreground";
    }
  };

  const filteredConversations = conversationHistory.filter(conversation => {
    const matchesSearch = conversation.summary.toLowerCase().includes(searchTerm.toLowerCase()) ||
      conversation.tags.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()));

    if (selectedFilter === "all") return matchesSearch;
    return matchesSearch && conversation.mood === selectedFilter;
  });

  const handleViewDetails = (conversation: any) => {
    setSelectedConversation(conversation);
  };

  const handleContinueConversation = (conversationId: string) => {
    navigate('/therapist', { state: { conversationId } });
  };

  const getMoodStats = (conversations: any[]) => {
    const moodCounts = { happy: 0, neutral: 0, sad: 0 };
    conversations.forEach(conv => {
      if (conv.mood && moodCounts.hasOwnProperty(conv.mood)) {
        moodCounts[conv.mood as keyof typeof moodCounts]++;
      }
    });
    return moodCounts;
  };

  return (
    <div className="min-h-screen relative flex flex-col bg-gradient-to-br from-primary/10 via-background to-secondary/10 selection:bg-primary/30 overflow-x-hidden">
      <BackgroundDecor />
      <Navigation />

      <main className="container mx-auto px-4 py-8 pb-20 md:pb-8">
        {/* Header */}
        <div className="mb-8 animate-fade-in-up">
          <h1 className="text-3xl font-bold text-foreground mb-2">
            Conversation History
          </h1>
          <p className="text-muted-foreground">
            Review your journey and track your progress with ELLA
          </p>
        </div>

        {/* Filters and Search */}
        <Card className="mb-6 animate-fade-in-up delay-100">
          <CardContent className="p-6">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search conversations or tags..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>

              <div className="flex gap-2">
                {["all", "happy", "neutral", "sad"].map((filter) => (
                  <Button
                    key={filter}
                    variant={selectedFilter === filter ? "default" : "outline"}
                    size="sm"
                    onClick={() => setSelectedFilter(filter)}
                    className="capitalize"
                  >
                    {filter === "all" ? (
                      <Filter className="mr-2 h-4 w-4" />
                    ) : (
                      <div className="mr-2">{getMoodIcon(filter)}</div>
                    )}
                    {filter}
                  </Button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Stats Overview */}
        <div className="grid md:grid-cols-3 gap-4 mb-8 animate-fade-in-up delay-200">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold text-foreground">
                    {statsLoading ? "..." : stats?.total_sessions || 0}
                  </p>
                  <p className="text-sm text-muted-foreground">Total Sessions</p>
                </div>
                <MessageCircle className="h-8 w-8 text-primary" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold text-foreground">
                    {statsLoading ? "..." : stats ? `${Math.floor(stats.total_minutes / 60)}h ${stats.total_minutes % 60}m` : "0h 0m"}
                  </p>
                  <p className="text-sm text-muted-foreground">Total Time</p>
                </div>
                <Calendar className="h-8 w-8 text-secondary" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold text-foreground">
                    {statsLoading ? "..." : stats?.current_streak || 0}
                  </p>
                  <p className="text-sm text-muted-foreground">Day Streak</p>
                </div>
                <Smile className="h-8 w-8 text-accent" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Conversation List */}
        <div className="space-y-4 animate-fade-in-up delay-300">
          {conversationsLoading ? (
            <div className="text-center py-8 text-muted-foreground">Loading conversations...</div>
          ) : filteredConversations.length === 0 ? (
            <div className="text-center py-12 animate-fade-in-up">
              <MessageCircle className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-foreground mb-2">
                No conversations found
              </h3>
              <p className="text-muted-foreground mb-4">
                {conversations.length === 0 ? "Start your first conversation with ELLA!" : "Try adjusting your search or filters"}
              </p>
              {conversations.length === 0 ? (
                <Button asChild>
                  <a href="/therapist">Start Conversation</a>
                </Button>
              ) : (
                <Button variant="outline" onClick={() => {
                  setSearchTerm("");
                  setSelectedFilter("all");
                }}>
                  Clear Filters
                </Button>
              )}
            </div>
          ) : (
            filteredConversations.map((conversation) => (
              <Card
                key={conversation.id}
                className={cn(
                  "cursor-pointer hover:shadow-glow transition-all duration-300 border-l-4",
                  getMoodColor(conversation.mood || 'neutral')
                )}
              >
                <CardContent className="p-6">
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        {getMoodIcon(conversation.mood || 'neutral')}
                        <span className="text-sm font-medium text-foreground">
                          {conversation.date.toLocaleDateString("en-US", {
                            weekday: 'long',
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric'
                          })}
                        </span>
                        <span className="text-sm text-muted-foreground">• {conversation.timeAgo}</span>
                      </div>

                      <p className="text-foreground mb-3 leading-relaxed">
                        {conversation.summary}
                      </p>

                      <div className="flex flex-wrap gap-2">
                        {conversation.tags.map((tag) => (
                          <span
                            key={tag}
                            className="px-2 py-1 bg-muted text-muted-foreground text-xs rounded-md"
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="flex md:flex-col gap-2">
                      <Dialog>
                        <DialogTrigger asChild>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleViewDetails(conversation)}
                          >
                            View Details
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-2xl">
                          <DialogHeader>
                            <DialogTitle>Conversation Details</DialogTitle>
                            <DialogDescription>
                              {conversation.date.toLocaleDateString("en-US", {
                                weekday: 'long',
                                year: 'numeric',
                                month: 'long',
                                day: 'numeric'
                              })} • {conversation.timeAgo}
                            </DialogDescription>
                          </DialogHeader>
                          <div className="space-y-4">
                            <div>
                              <h4 className="font-semibold mb-2 flex items-center">
                                {getMoodIcon(conversation.mood || 'neutral')}
                                <span className="ml-2">Mood Analysis</span>
                              </h4>
                              <div className="bg-muted p-4 rounded-lg">
                                <p className="text-sm text-muted-foreground mb-2">
                                  Detected mood: <span className="font-medium capitalize">{conversation.mood || 'neutral'}</span>
                                </p>
                                <div className="grid grid-cols-3 gap-4 text-center">
                                  {Object.entries(getMoodStats([conversation])).map(([mood, count]) => (
                                    <div key={mood} className="flex flex-col items-center">
                                      {getMoodIcon(mood)}
                                      <span className="text-xs text-muted-foreground mt-1 capitalize">{mood}</span>
                                      <span className="text-sm font-medium">{count > 0 ? '✓' : '—'}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            </div>

                            <div>
                              <h4 className="font-semibold mb-2">Summary</h4>
                              <p className="text-sm text-muted-foreground bg-muted p-4 rounded-lg">
                                {conversation.summary}
                              </p>
                            </div>

                            <div>
                              <h4 className="font-semibold mb-2">Topics Discussed</h4>
                              <div className="flex flex-wrap gap-2">
                                {conversation.tags.map((tag) => (
                                  <span
                                    key={tag}
                                    className="px-3 py-1 bg-primary/10 text-primary text-sm rounded-full"
                                  >
                                    #{tag}
                                  </span>
                                ))}
                              </div>
                            </div>

                            {conversation.messages && conversation.messages.length > 0 && (
                              <div>
                                <h4 className="font-semibold mb-2">Conversation Preview</h4>
                                <div className="max-h-40 overflow-y-auto bg-muted p-4 rounded-lg space-y-2">
                                  {conversation.messages.slice(0, 3).map((msg: any, idx: number) => (
                                    <div key={idx} className="text-sm">
                                      <span className="font-medium">{msg.is_user ? 'You' : 'ELLA'}:</span>
                                      <span className="text-muted-foreground ml-2">
                                        {msg.content.length > 100 ? msg.content.substring(0, 100) + '...' : msg.content}
                                      </span>
                                    </div>
                                  ))}
                                  {conversation.messages.length > 3 && (
                                    <p className="text-xs text-muted-foreground">
                                      ... and {conversation.messages.length - 3} more messages
                                    </p>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        </DialogContent>
                      </Dialog>

                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleContinueConversation(conversation.id)}
                      >
                        Continue
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>

      </main>

      <MobileNavigation />
    </div>
  );
}