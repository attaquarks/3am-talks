import { useEffect, useState } from 'react';
import { useToast } from '@/hooks/use-toast';
import { supabase } from '@/integrations/supabase/client';

interface UserStats {
  id: string;
  user_id: string;
  current_streak: number;
  total_sessions: number;
  total_minutes: number;
  mood_improvement_percentage: number;
  last_session_date: string | null;
  created_at: string;
  updated_at: string;
}

export function useUserStats() {
  const [stats, setStats] = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    fetchUserStats();
    
    // Set up real-time subscription for user_stats updates
    const setupSubscription = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (user) {
        const subscription = supabase
          .channel('user_stats_changes')
          .on(
            'postgres_changes',
            {
              event: 'UPDATE',
              schema: 'public',
              table: 'user_stats',
              filter: `user_id=eq.${user.id}`
            },
            (payload) => {
              setStats(payload.new as UserStats);
            }
          )
          .subscribe();

        return () => {
          subscription.unsubscribe();
        };
      }
    };

    setupSubscription();
  }, []);

  const fetchUserStats = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error('Not authenticated');

      const { data, error } = await supabase
        .from('user_stats')
        .select('*')
        .eq('user_id', user.id)
        .single();

      if (error) throw error;
      setStats(data);
    } catch (error) {
      console.error('Error fetching user stats:', error);
      toast({
        title: "Error",
        description: "Failed to fetch user statistics.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  // Calculate current streak based on daily logins
  const calculateCurrentStreak = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return 0;

      // Get current user stats
      const { data: userStats } = await supabase
        .from('user_stats')
        .select('last_session_date, current_streak')
        .eq('user_id', user.id)
        .single();

      if (!userStats) return 0;

      const today = new Date().toISOString().split('T')[0];
      const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString().split('T')[0];
      
      // If last_session_date is today, don't recalculate streak
      if (userStats.last_session_date === today) {
        return userStats.current_streak;
      }
      
      // If last_session_date is yesterday, increment streak
      if (userStats.last_session_date === yesterday) {
        return userStats.current_streak + 1;
      }
      
      // If last_session_date is before yesterday, reset to 1
      return 1;
    } catch (error) {
      console.error('Error calculating streak:', error);
      return 0;
    }
  };

  // Calculate mood improvement percentage
  const calculateMoodImprovement = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return 0;

      const { data: moodEntries } = await supabase
        .from('mood_entries')
        .select('mood, date')
        .eq('user_id', user.id)
        .order('date', { ascending: true });

      if (!moodEntries || moodEntries.length < 2) return 0;

      // Assign scores to moods
      const moodScores: { [key: string]: number } = {
        'very_sad': 1,
        'sad': 2,
        'neutral': 3,
        'happy': 4,
        'very_happy': 5
      };

      const scores = moodEntries.map(entry => moodScores[entry.mood] || 3);
      const firstScore = scores[0];
      const lastScore = scores[scores.length - 1];

      if (firstScore === 0) return 0;
      
      const improvement = ((lastScore - firstScore) / firstScore) * 100;
      return Math.round(improvement);
    } catch (error) {
      console.error('Error calculating mood improvement:', error);
      return 0;
    }
  };

  // Calculate total sessions
  const calculateTotalSessions = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return 0;

      const { count } = await supabase
        .from('conversations')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', user.id);

      return count || 0;
    } catch (error) {
      console.error('Error calculating total sessions:', error);
      return 0;
    }
  };

  const updateStats = async (updates: Partial<Pick<UserStats, 'current_streak' | 'total_sessions' | 'total_minutes' | 'mood_improvement_percentage' | 'last_session_date'>>) => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error('Not authenticated');

      // Only calculate values that are explicitly requested or not provided
      let finalUpdates = { ...updates };
      
      // Only calculate mood improvement if not provided
      if (!updates.mood_improvement_percentage) {
        finalUpdates.mood_improvement_percentage = await calculateMoodImprovement();
      }

      // Only calculate total sessions if not provided
      if (!updates.total_sessions) {
        finalUpdates.total_sessions = await calculateTotalSessions();
      }

      // If updating total_minutes, add to existing value
      if (updates.total_minutes && stats) {
        finalUpdates.total_minutes = stats.total_minutes + updates.total_minutes;
      }

      const { data, error } = await supabase
        .from('user_stats')
        .update(finalUpdates)
        .eq('user_id', user.id)
        .select()
        .single();

      if (error) throw error;
      setStats(data);
    } catch (error) {
      console.error('Error updating user stats:', error);
      // Don't show toast for stats errors to avoid UI clutter
    }
  };

  const updateCurrentStreak = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error('Not authenticated');

      const currentStreak = await calculateCurrentStreak();
      
      const { data, error } = await supabase
        .from('user_stats')
        .update({ current_streak: currentStreak })
        .eq('user_id', user.id)
        .select()
        .single();

      if (error) throw error;
      setStats(data);
    } catch (error) {
      console.error('Error updating current streak:', error);
    }
  };

  const refreshStats = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error('Not authenticated');

      // Recalculate all stats
      const currentStreak = await calculateCurrentStreak();
      const moodImprovement = await calculateMoodImprovement();
      const totalSessions = await calculateTotalSessions();

      // Only update if values have actually changed
      const updates: any = {};
      
      if (currentStreak !== stats?.current_streak) {
        updates.current_streak = currentStreak;
      }
      
      if (moodImprovement !== stats?.mood_improvement_percentage) {
        updates.mood_improvement_percentage = moodImprovement;
      }
      
      if (totalSessions !== stats?.total_sessions) {
        updates.total_sessions = totalSessions;
      }

      // Only update if there are changes
      if (Object.keys(updates).length > 0) {
        const { data, error } = await supabase
          .from('user_stats')
          .update(updates)
          .eq('user_id', user.id)
          .select()
          .single();

        if (error) throw error;
        setStats(data);
      }
    } catch (error) {
      console.error('Error refreshing stats:', error);
    }
  };

  return { stats, loading, updateStats, updateCurrentStreak, refreshStats, refetch: fetchUserStats };
}