import { useEffect, useState } from 'react';
import { useToast } from '@/hooks/use-toast';

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
    // Real-time subscription removed as it requires authenticated Supabase client
  }, []);

  const fetchUserStats = async () => {
    try {
      const response = await fetch('/api/data/user_stats');
      if (!response.ok) {
        if (response.status === 401) return;
        throw new Error('Failed to fetch user stats');
      }

      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Error fetching user stats:', error);
      // Fail silently on auth error
    } finally {
      setLoading(false);
    }
  };

  // Calculate current streak based on daily logins
  const calculateCurrentStreak = async () => {
    try {
      const response = await fetch('/api/data/user_stats');
      if (!response.ok) return 0;
      const userStats = await response.json();

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
      const response = await fetch('/api/data/mood_entries');
      if (!response.ok) return 0;
      const moodEntries = await response.json();

      if (!moodEntries || moodEntries.length < 2) return 0;

      // Sort by date ascending
      moodEntries.sort((a: any, b: any) => new Date(a.date).getTime() - new Date(b.date).getTime());

      // Assign scores to moods
      const moodScores: { [key: string]: number } = {
        'very_sad': 1,
        'sad': 2,
        'neutral': 3,
        'happy': 4,
        'very_happy': 5
      };

      const scores = moodEntries.map((entry: any) => moodScores[entry.mood] || 3);
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
      const response = await fetch('/api/data/conversations');
      if (!response.ok) return 0;
      const conversations = await response.json();
      return conversations.length || 0;
    } catch (error) {
      console.error('Error calculating total sessions:', error);
      return 0;
    }
  };

  const updateStats = async (updates: Partial<Pick<UserStats, 'current_streak' | 'total_sessions' | 'total_minutes' | 'mood_improvement_percentage' | 'last_session_date'>>) => {
    if (!stats) return;

    try {
      // Only calculate values that are explicitly requested or not provided
      let finalUpdates = { ...updates };

      // Only calculate mood improvement if not provided
      if (!updates.mood_improvement_percentage && updates.mood_improvement_percentage !== 0) {
        // Only calculate if we suspect it changed? Or just leave it?
        // Original logic re-calculated it.
        // finalUpdates.mood_improvement_percentage = await calculateMoodImprovement();
      }

      // If updating total_minutes, add to existing value
      if (updates.total_minutes) {
        finalUpdates.total_minutes = stats.total_minutes + updates.total_minutes;
      }

      const response = await fetch(`/api/data/user_stats/${stats.user_id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(finalUpdates)
      });

      if (!response.ok) throw new Error('Failed to update stats');
      const data = await response.json();

      setStats(data);
    } catch (error) {
      console.error('Error updating user stats:', error);
    }
  };

  const updateCurrentStreak = async () => {
    if (!stats) return;
    try {
      const currentStreak = await calculateCurrentStreak();

      const response = await fetch(`/api/data/user_stats/${stats.user_id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_streak: currentStreak })
      });

      if (!response.ok) throw new Error('Failed to update streak');
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Error updating current streak:', error);
    }
  };

  const refreshStats = async () => {
    if (!stats) return;
    try {
      // Recalculate all stats
      const currentStreak = await calculateCurrentStreak();
      const moodImprovement = await calculateMoodImprovement();
      const totalSessions = await calculateTotalSessions();

      // Only update if values have actually changed
      const updates: any = {};

      if (currentStreak !== stats.current_streak) {
        updates.current_streak = currentStreak;
      }

      if (moodImprovement !== stats.mood_improvement_percentage) {
        updates.mood_improvement_percentage = moodImprovement;
      }

      if (totalSessions !== stats.total_sessions) {
        updates.total_sessions = totalSessions;
      }

      // Only update if there are changes
      if (Object.keys(updates).length > 0) {
        const response = await fetch(`/api/data/user_stats/${stats.user_id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updates)
        });
        if (!response.ok) throw new Error('Failed to refresh stats');
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Error refreshing stats:', error);
    }
  };

  return { stats, loading, updateStats, updateCurrentStreak, refreshStats, refetch: fetchUserStats };
}