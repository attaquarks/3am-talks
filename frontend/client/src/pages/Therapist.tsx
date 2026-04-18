import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
// import { supabase } from '@/integrations/supabase/client'; // Removed
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Navigation, MobileNavigation } from "@/components/Navigation";
import BackgroundDecor from '@/components/auth/BackgroundDecor';
import VoiceCall from '@/components/VoiceCall';
import { Send, Mic, MicOff, MoreVertical, RotateCcw, Clock, Smile, Meh, Frown, MessageCircle, Sparkles, Heart, Brain, Zap, Moon, Sun, Bot, User, ArrowLeft, Plus, Trash2, Edit3, Copy, Check, ChevronDown, Phone } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUserStats } from "@/hooks/useUserStats";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useTheme } from "@/components/ThemeProvider";
import { CrisisCountdownModal } from "@/components/CrisisCountdownModal";

interface Message {
  id: string;
  conversation_id: string;
  content: string;
  is_user: boolean;
  created_at: string;
  is_crisis?: boolean;
}

interface Conversation {
  id: string;
  user_id: string;
  title: string | null;
  mood: string | null;
  summary: string | null;
  tags: string[] | null;
  duration_minutes: number | null;
  created_at: string;
  updated_at: string;
}

export default function Therapist() {
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const messagesAbortRef = useRef<AbortController | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [currentMood, setCurrentMood] = useState<'happy' | 'neutral' | 'sad'>('neutral');
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [sessionStartTime, setSessionStartTime] = useState<Date | null>(null);
  const [countdownState, setCountdownState] = useState<{ open: boolean; seconds: number }>({ open: false, seconds: 30 });
  const [sessionDuration, setSessionDuration] = useState(0);
  const [showSidebar, setShowSidebar] = useState(true);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const sessionTimerRef = useRef<NodeJS.Timeout | null>(null);
  const dailyLoginRecordedRef = useRef<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const { updateStats } = useUserStats();
  const { toast } = useToast();
  const { theme } = useTheme();

  // Prevent body scrolling when component mounts
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);

  // Session timer effect
  useEffect(() => {
    if (sessionStartTime) {
      sessionTimerRef.current = setInterval(() => {
        const now = new Date();
        const duration = Math.floor((now.getTime() - sessionStartTime.getTime()) / 1000 / 60);
        setSessionDuration(duration);
      }, 60000); // Update every minute
    }

    return () => {
      if (sessionTimerRef.current) {
        clearInterval(sessionTimerRef.current);
      }
    };
  }, [sessionStartTime]);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const res = await fetch('/api/user');
        if (!res.ok) {
          navigate('/auth');
          return;
        }
        const user = await res.json();
        setCurrentUser(user);
        await loadConversations();
      } catch (error) {
        console.error('Auth check error:', error);
        navigate('/auth');
      }
    };

    checkAuth();
  }, [navigate]);

  const loadConversations = async () => {
    try {
      const response = await fetch('/api/data/conversations?order=created_at.desc');

      if (!response.ok) {
        throw new Error('Failed to load conversations');
      }

      const data = await response.json();
      setConversations(data || []);
    } catch (error) {
      console.error('Error loading conversations:', error);
      toast({
        title: "Error",
        description: "Failed to load conversations.",
        variant: "destructive"
      });
    }
  };

  const loadMessages = useCallback(async (conversationId: string) => {
    // Cancel any in-flight message fetch to prevent stale data from overwriting
    if (messagesAbortRef.current) {
      messagesAbortRef.current.abort();
    }
    const controller = new AbortController();
    messagesAbortRef.current = controller;

    try {
      const response = await fetch(
        `/api/data/messages?conversation_id=eq.${conversationId}&order=created_at.asc`,
        { signal: controller.signal }
      );

      if (!response.ok) {
        throw new Error('Failed to load messages');
      }

      const data = await response.json();
      // Only update state if this request wasn't aborted
      if (!controller.signal.aborted) {
        setMessages(data || []);
      }
    } catch (error: any) {
      if (error?.name === 'AbortError') return; // Expected when switching conversations
      console.error('Error loading messages:', error);
      toast({
        title: "Error",
        description: "Failed to load messages.",
        variant: "destructive"
      });
    }
  }, [toast]);

  const detectMoodFromText = (text: string): 'happy' | 'neutral' | 'sad' => {
    const lowerText = text.toLowerCase();

    const happyWords = ['happy', 'joy', 'excited', 'great', 'wonderful', 'amazing', 'fantastic', 'good', 'positive', 'optimistic', 'grateful', 'blessed', 'lucky', 'thrilled', 'delighted'];
    const sadWords = ['sad', 'depressed', 'anxious', 'worried', 'stressed', 'angry', 'frustrated', 'hopeless', 'lonely', 'tired', 'exhausted', 'overwhelmed', 'scared', 'fear', 'pain', 'hurt'];

    const happyCount = happyWords.filter(word => lowerText.includes(word)).length;
    const sadCount = sadWords.filter(word => lowerText.includes(word)).length;

    if (happyCount > sadCount) return 'happy';
    if (sadCount > happyCount) return 'sad';
    return 'neutral';
  };

  const generateSummary = (messages: Message[]): string => {
    const userMessages = messages.filter(m => m.is_user).map(m => m.content);
    if (userMessages.length === 0) return "New chat";

    const allText = userMessages.join(' ').toLowerCase();

    const topics = [];
    if (allText.includes('work') || allText.includes('job') || allText.includes('career')) topics.push('work');
    if (allText.includes('relationship') || allText.includes('partner') || allText.includes('family')) topics.push('relationships');
    if (allText.includes('anxiety') || allText.includes('stress') || allText.includes('worry')) topics.push('anxiety');
    if (allText.includes('depression') || allText.includes('sad') || allText.includes('down')) topics.push('mood');
    if (allText.includes('sleep') || allText.includes('tired') || allText.includes('rest')) topics.push('sleep');

    if (topics.length > 0) {
      return topics.slice(0, 2).join(" & ") + " talk";
    }

    return userMessages[0].split(/\s+/).slice(0, 5).join(" ");
  };

  const extractTagsFromMessages = (userMessages: string[]) => {
    const allText = userMessages.join(' ').toLowerCase();
    const tags: string[] = [];

    // Common therapy-related tags
    const tagKeywords = {
      'anxiety': ['anxious', 'anxiety', 'worried', 'nervous', 'panic'],
      'depression': ['depressed', 'depression', 'sad', 'down', 'hopeless'],
      'stress': ['stress', 'stressed', 'pressure', 'overwhelmed'],
      'relationships': ['relationship', 'partner', 'friend', 'family', 'love'],
      'work': ['work', 'job', 'career', 'boss', 'colleague'],
      'self-care': ['tired', 'sleep', 'eating', 'exercise', 'health'],
      'emotions': ['feeling', 'emotion', 'mood', 'angry', 'frustrated']
    };

    Object.entries(tagKeywords).forEach(([tag, keywords]) => {
      if (keywords.some(keyword => allText.includes(keyword))) {
        tags.push(tag);
      }
    });

    return tags;
  };

  const scrollToBottom = () => {
    const messagesContainer = messagesEndRef.current?.parentElement;
    if (messagesContainer) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  };

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    setShowScrollButton(!isAtBottom);
  };

  // Remove auto-scroll completely
  // useEffect(() => {
  //   // Only scroll to bottom when new messages are added, not on every render
  //   if (messages.length > 0) {
  //     const timer = setTimeout(() => {
  //       scrollToBottom();
  //     }, 100);
  //     return () => clearTimeout(timer);
  //   }
  // }, [messages]);

  const startSession = () => {
    setSessionStartTime(new Date());
    setSessionDuration(0);
  };

  const endSession = async () => {
    if (sessionStartTime && currentConversationId) {
      const endTime = new Date();
      const duration = Math.floor((endTime.getTime() - sessionStartTime.getTime()) / 1000 / 60);

      try {
        // Update conversation duration using PATCH
        const response = await fetch(`/api/data/conversations/${currentConversationId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ duration_minutes: duration })
        });

        if (!response.ok) {
          console.error('Error updating conversation duration');
        }

        // Update user stats
        await updateStats({
          total_minutes: duration,
          last_session_date: new Date().toISOString().split('T')[0]
        });

        setSessionStartTime(null);
        setSessionDuration(0);
      } catch (error) {
        console.error('Error ending session:', error);
      }
    }
  };

  const copyMessage = async (content: string, messageId: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedMessageId(messageId);
      toast({
        title: "Copied!",
        description: "Message copied to clipboard.",
      });
      setTimeout(() => setCopiedMessageId(null), 2000);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to copy message.",
        variant: "destructive"
      });
    }
  };

  const sendMessage = async () => {
    if (!message.trim() || isLoading || !currentUser) return;

    const userMessage = message;
    setMessage('');
    setIsLoading(true);

    try {
      // Optimistically add user message to UI
      const tempUserMsgId = Date.now().toString();
      const optimisticUserMsg: Message = {
        id: tempUserMsgId,
        conversation_id: currentConversationId || 'temp',
        content: userMessage,
        is_user: true,
        created_at: new Date().toISOString()
      };
      setMessages(prev => [...prev, optimisticUserMsg]);

      // Detect mood locally for UI feedback
      const detectedMood = detectMoodFromText(userMessage);
      setCurrentMood(detectedMood);

      let activeConversationId = currentConversationId;

      // Start session timer if new conversation/session
      if (!sessionStartTime) {
        startSession();
      }

      // Send to Backend API
      const payload: any = { message: userMessage };
      if (currentConversationId) {
        payload.conversation_id = currentConversationId;
      }

      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error('Failed to get AI response');
      }

      const data = await response.json();
      const aiMessageContent = data.response;
      // Backend returns conversation_id (might be new if we started one)
      activeConversationId = data.conversation_id;

      if (!currentConversationId) {
        setCurrentConversationId(activeConversationId);

        const title = generateTitle(userMessage);
        fetch(`/api/data/conversations/${activeConversationId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title })
        }).catch(() => {});

        loadConversations();

        // Update user stats for new session
        await updateStats({
          total_sessions: 1,
          last_session_date: new Date().toISOString().split('T')[0]
        });
      }

      // Add AI message to UI
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        conversation_id: activeConversationId || 'temp', // Should be valid now
        content: aiMessageContent,
        is_user: false,
        created_at: new Date().toISOString(),
        is_crisis: !!data.crisis?.detected,
      };
      setMessages(prev => [...prev, aiMsg]);

      // If a cancellable countdown was kicked off server-side, open the modal.
      if (data.crisis?.countdown?.seconds) {
        setCountdownState({ open: true, seconds: data.crisis.countdown.seconds });
      }

    } catch (error) {
      console.error('Error sending message:', error);
      toast({
        title: "Error",
        description: "Failed to send message. Please try again.",
        variant: "destructive"
      });
      // Optionally remove optimistic message or show error state
    } finally {
      setIsLoading(false);
    }
  };

  const startNewConversation = async () => {
    // End current session if exists
    if (sessionStartTime) {
      await endSession();
    }

    try {
      const response = await fetch('/api/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) throw new Error('Failed to start session');

      const data = await response.json();
      setCurrentConversationId(data.conversation_id);
      setMessages([]);
      setCurrentMood('neutral');
      setShowSidebar(false);
    } catch (error) {
      console.error('Error starting new conversation:', error);
      setCurrentConversationId(null);
      setMessages([]);
      setCurrentMood('neutral');
      setShowSidebar(false);
    }
  };

  const selectConversation = (conversation: Conversation) => {
    setCurrentConversationId(conversation.id);
    loadMessages(conversation.id);
    setShowSidebar(false);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const toggleListening = () => {
    setIsListening(!isListening);
    // TODO: Implement voice recognition
  };

  const getMoodIcon = (mood: string) => {
    switch (mood) {
      case "happy":
        return <Smile className="h-4 w-4 text-green-500" />;
      case "neutral":
        return <Meh className="h-4 w-4 text-yellow-500" />;
      case "sad":
        return <Frown className="h-4 w-4 text-red-500" />;
      default:
        return <Meh className="h-4 w-4 text-gray-500" />;
    }
  };

  const formatDuration = (minutes: number) => {
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };

  const getCurrentConversation = () => {
    return conversations.find(c => c.id === currentConversationId);
  };

  const deleteConversation = async (e: React.MouseEvent, conversationId: string) => {
    e.stopPropagation();
    try {
      const res = await fetch(`/api/data/conversations/${conversationId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error();
      if (currentConversationId === conversationId) {
        setCurrentConversationId(null);
        setMessages([]);
      }
      setConversations(prev => prev.filter(c => c.id !== conversationId));
      toast({ title: "Deleted", description: "Conversation removed." });
    } catch {
      toast({ title: "Error", description: "Failed to delete conversation.", variant: "destructive" });
    }
  };

  const generateTitle = (text: string): string => {
    const words = text.trim().split(/\s+/).slice(0, 5).join(" ");
    return words.length > 30 ? words.substring(0, 30) + "…" : words;
  };

  return (
    <div className="h-screen overflow-hidden bg-gradient-to-br from-primary/10 via-background to-secondary/10 selection:bg-primary/30 relative flex flex-col">
      <BackgroundDecor />
      <Navigation />
      <MobileNavigation />

      <div className="flex-1 min-h-0 container mx-auto px-4 py-2 max-w-7xl">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 h-full">
          {/* Conversations Sidebar */}
          <div className={cn(
            "lg:col-span-1 min-h-0",
            showSidebar ? "block" : "hidden lg:block"
          )}>
            <div className="h-full flex flex-col bg-card/50 backdrop-blur-sm border border-border/50 shadow-xl rounded-xl">
              <div className="flex items-center justify-between p-4 border-b border-border/50">
                <div className="flex items-center space-x-2">
                  <div className="w-7 h-7 bg-gradient-to-r from-primary to-primary/70 rounded-lg flex items-center justify-center">
                    <MessageCircle className="w-3.5 h-3.5 text-primary-foreground" />
                  </div>
                  <h2 className="text-sm font-semibold text-foreground">Chats</h2>
                </div>
                <Button onClick={startNewConversation} size="sm" variant="ghost" className="h-7 w-7 p-0">
                  <Plus className="w-4 h-4" />
                </Button>
              </div>

              <ScrollArea className="flex-1 min-h-0">
                <div className="p-2 space-y-1">
                  {conversations.length === 0 ? (
                    <div className="text-center py-8 px-4">
                      <MessageCircle className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
                      <p className="text-xs text-muted-foreground">No conversations yet</p>
                    </div>
                  ) : (
                    conversations.map((conversation) => {
                      const title = conversation.title || "New chat";
                      const shortTitle = title.split(/\s+/).slice(0, 5).join(" ") + (title.split(/\s+/).length > 5 ? "…" : "");
                      return (
                        <div
                          key={conversation.id}
                          onClick={() => selectConversation(conversation)}
                          className={cn(
                            "group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-all duration-150",
                            currentConversationId === conversation.id
                              ? "bg-primary/10 border border-primary/20"
                              : "hover:bg-muted/50 border border-transparent"
                          )}
                        >
                          <div className="flex-1 min-w-0">
                            <h3 className="text-sm text-foreground truncate group-hover:text-primary transition-colors">
                              {shortTitle}
                            </h3>
                            <span className="text-xs text-muted-foreground">
                              {new Date(conversation.created_at).toLocaleDateString()}
                            </span>
                          </div>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 ml-1 text-muted-foreground hover:text-destructive"
                            onClick={(e) => deleteConversation(e, conversation.id)}
                          >
                            <Trash2 className="w-3 h-3" />
                          </Button>
                        </div>
                      );
                    })
                  )}
                </div>
              </ScrollArea>
            </div>
          </div>

          {/* Chat Area */}
          <div className="lg:col-span-3 min-h-0">
            <div className="h-full flex flex-col bg-card/50 backdrop-blur-sm border border-border/50 shadow-xl rounded-xl overflow-hidden">
              {/* Chat Header */}
              <div className="px-4 py-3 border-b border-border/50 bg-gradient-to-r from-card to-card/80 flex-shrink-0">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="relative">
                      <Avatar className="w-10 h-10 ring-2 ring-primary/20">
                        <AvatarImage src="/ella-avatar.png" />
                        <AvatarFallback className="bg-gradient-to-r from-primary to-primary/70 text-primary-foreground">
                          <Bot className="w-5 h-5" />
                        </AvatarFallback>
                      </Avatar>
                      <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-green-500 rounded-full border-2 border-background"></div>
                    </div>
                    <div>
                      <h1 className="text-lg font-bold text-foreground flex items-center space-x-2">
                        <span>ELLA</span>
                        <Sparkles className="w-4 h-4 text-primary animate-pulse" />
                      </h1>
                      <p className="text-xs text-muted-foreground">AI Therapist & Mental Health Companion</p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    {sessionStartTime && (
                      <div className="flex items-center text-xs text-muted-foreground px-2 py-1 bg-muted/50 rounded-full">
                        <Clock className="w-3 h-3 mr-1" />
                        {sessionDuration}m
                      </div>
                    )}
                    <VoiceCall />
                    <Button
                      onClick={() => setShowSidebar(!showSidebar)}
                      variant="outline"
                      size="sm"
                      className="lg:hidden h-8 w-8 p-0"
                    >
                      <ArrowLeft className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 min-h-0 overflow-y-auto relative" onScroll={handleScroll}>
                <div className="p-4 space-y-4" ref={messagesEndRef}>
                  {messages.length === 0 ? (
                    <div className="text-center py-12">
                      <div className="w-16 h-16 bg-gradient-to-r from-primary/10 to-primary/20 rounded-full flex items-center justify-center mx-auto mb-4">
                        <MessageCircle className="w-8 h-8 text-primary" />
                      </div>
                      <h3 className="text-lg font-semibold text-foreground mb-2">Welcome to ELLA</h3>
                      <p className="text-sm text-muted-foreground mb-4 max-w-md mx-auto">
                        Share your thoughts, feelings, or concerns and I'll help you work through them.
                      </p>
                      <div className="flex flex-wrap justify-center gap-2 max-w-lg mx-auto">
                        {[
                          "I'm feeling anxious today",
                          "I need help with stress",
                          "I want to talk about my mood",
                          "I'm having relationship issues"
                        ].map((suggestion, index) => (
                          <Button
                            key={index}
                            variant="outline"
                            size="sm"
                            onClick={() => setMessage(suggestion)}
                            className="text-xs"
                          >
                            {suggestion}
                          </Button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    messages.map((msg) => (
                      <div
                        key={msg.id}
                        className={cn(
                          "flex items-start space-x-3",
                          msg.is_user ? "flex-row-reverse space-x-reverse" : ""
                        )}
                      >
                        <Avatar className={cn(
                          "w-7 h-7 ring-2 flex-shrink-0",
                          msg.is_user ? "ring-primary/20" : "ring-primary/10"
                        )}>
                          <AvatarFallback className={cn(
                            "text-xs",
                            msg.is_user
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted text-muted-foreground"
                          )}>
                            {msg.is_user ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
                          </AvatarFallback>
                        </Avatar>

                        <div className={cn(
                          "max-w-[80%] space-y-1",
                          msg.is_user ? "text-right" : ""
                        )}>
                          <div className={cn(
                            "group relative rounded-2xl px-4 py-2.5 shadow-sm",
                            msg.is_user
                              ? "bg-primary text-primary-foreground ml-auto"
                              : msg.is_crisis
                                ? "bg-rose-50 dark:bg-rose-950/30 border border-rose-300 dark:border-rose-900/60 text-foreground"
                                : "bg-muted/50 text-foreground"
                          )}>
                            {msg.is_crisis && !msg.is_user && (
                              <div className="text-xs font-semibold text-rose-600 dark:text-rose-400 mb-1 flex items-center gap-1">
                                Safety response
                              </div>
                            )}
                            <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                            <div className={cn(
                              "absolute top-1 opacity-0 group-hover:opacity-100 transition-opacity",
                              msg.is_user ? "left-1" : "right-1"
                            )}>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-5 w-5 p-0"
                                onClick={() => copyMessage(msg.content, msg.id)}
                              >
                                {copiedMessageId === msg.id ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                              </Button>
                            </div>
                          </div>
                          <div className={cn("text-xs text-muted-foreground", msg.is_user ? "text-right" : "text-left")}>
                            {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </div>
                        </div>
                      </div>
                    ))
                  )}

                  {isLoading && (
                    <div className="flex items-start space-x-3">
                      <Avatar className="w-7 h-7 ring-2 ring-primary/10">
                        <AvatarFallback className="bg-muted text-muted-foreground">
                          <Bot className="w-3.5 h-3.5" />
                        </AvatarFallback>
                      </Avatar>
                      <div className="bg-muted/50 rounded-2xl px-4 py-3 shadow-sm">
                        <div className="flex space-x-1">
                          <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce"></div>
                          <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                          <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {showScrollButton && messages.length > 0 && (
                  <Button
                    onClick={scrollToBottom}
                    size="sm"
                    className="absolute bottom-3 right-3 w-8 h-8 rounded-full bg-primary/90 hover:bg-primary text-primary-foreground shadow-lg p-0"
                  >
                    <ChevronDown className="w-4 h-4" />
                  </Button>
                )}
              </div>

              {/* Input Area */}
              <div className="px-4 py-3 border-t border-border/50 bg-card/80 flex-shrink-0">
                <div className="flex items-center space-x-2">
                  <Input
                    ref={inputRef}
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Share your thoughts…"
                    className="flex-1 py-2.5 text-sm border-border/50 focus:border-primary/50"
                    disabled={isLoading}
                  />
                  <Button
                    onClick={sendMessage}
                    disabled={!message.trim() || isLoading}
                    size="sm"
                    className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-md px-4 h-9"
                  >
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <CrisisCountdownModal
        open={countdownState.open}
        seconds={countdownState.seconds}
        onClose={() => setCountdownState((s) => ({ ...s, open: false }))}
      />
    </div>
  );
}