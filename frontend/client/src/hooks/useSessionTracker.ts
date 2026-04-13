import { useEffect, useState, useRef } from 'react';
import { useAuth } from '@/hooks/useAuth';

export function useSessionTracker() {
  const { user } = useAuth();
  const [isActive, setIsActive] = useState(false);
  const sessionStartRef = useRef<number | null>(null);
  const lastActivityRef = useRef<number>(Date.now());
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const sessionTimerRef = useRef<NodeJS.Timeout | null>(null);
  const dailyLoginRecordedRef = useRef<string | null>(null);

  const startSession = async () => {
    if (!user) return;
    console.log('Starting session...');
    setIsActive(true);
    sessionStartRef.current = Date.now();
    lastActivityRef.current = Date.now();

    // Record daily login for streak tracking (only once per day)
    await recordDailyLogin();

    // Start session timer to update stats every minute
    sessionTimerRef.current = setInterval(async () => {
      if (isActive && sessionStartRef.current) {
        const sessionDuration = Math.floor((Date.now() - sessionStartRef.current) / 1000 / 60);
        if (sessionDuration > 0) {
          console.log(`Updating session time: ${sessionDuration} minutes`);
          await updateSessionTime(sessionDuration);
          sessionStartRef.current = Date.now(); // Reset timer to accumulate next minute
        }
      }
    }, 60000); // Update every minute
  };

  const endSession = async (persistStats = true) => {
    if (!isActive || !sessionStartRef.current) return;

    const sessionDuration = Math.floor((Date.now() - sessionStartRef.current) / 1000 / 60);

    // On logout/account deletion we end locally and skip network writes,
    // otherwise /api/data/user_stats races with cleared auth cookie.
    if (persistStats && sessionDuration > 0) {
      await updateSessionTime(sessionDuration);
    }

    setIsActive(false);
    sessionStartRef.current = null;

    if (sessionTimerRef.current) {
      clearInterval(sessionTimerRef.current);
      sessionTimerRef.current = null;
    }
  };

  const updateActivity = () => {
    lastActivityRef.current = Date.now();
  };

  const recordDailyLogin = async () => {
    try {
      if (!user) return;

      const today = new Date().toISOString().split('T')[0];

      // Check if we already recorded today's login
      if (dailyLoginRecordedRef.current === today) {
        return;
      }

      // Stats row is created on the server at login/OAuth; updates must use PATCH, not POST
      // (POST insert races and returns 409 when the row already exists).
      const response = await fetch('/api/data/user_stats');
      if (!response.ok) return;
      const currentStats = await response.json();

      if (currentStats.last_session_date === today) {
        dailyLoginRecordedRef.current = today;
        return;
      }

      const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString().split('T')[0];

      const updates: Record<string, number | string> = { last_session_date: today };

      if (currentStats.last_session_date === yesterday) {
        updates.current_streak = (currentStats.current_streak || 0) + 1;
      } else {
        updates.current_streak = 1;
      }

      const patchRes = await fetch(`/api/data/user_stats/${user.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (!patchRes.ok) {
        console.error('Failed to record daily login (patch user_stats):', patchRes.status);
        return;
      }

      dailyLoginRecordedRef.current = today;
    } catch (error) {
      console.error('Error recording daily login:', error);
    }
  };

  const updateSessionTime = async (minutes: number) => {
    try {
      if (!user || minutes <= 0) return;

      // Get current total_minutes first
      const response = await fetch('/api/data/user_stats');
      if (!response.ok) return;
      const currentStats = await response.json();

      const currentTotalMinutes = currentStats?.total_minutes || 0;
      const newTotalMinutes = currentTotalMinutes + minutes;
      const today = new Date().toISOString().split('T')[0];

      const patchRes = await fetch(`/api/data/user_stats/${user.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          total_minutes: newTotalMinutes,
          last_session_date: today,
        }),
      });
      if (!patchRes.ok) {
        console.error('Failed to update session time (patch user_stats):', patchRes.status);
      }
    } catch (error) {
      console.error('Error updating session time:', error);
    }
  };

  // Listen for auth state changes via useAuth's user object
  useEffect(() => {
    if (user) {
      startSession();
    } else {
      void endSession(false);
      dailyLoginRecordedRef.current = null;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  // Activity listeners
  useEffect(() => {
    const handleActivity = () => updateActivity();

    const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
    events.forEach(event => document.addEventListener(event, handleActivity, true));

    // Check for inactivity every minute
    intervalRef.current = setInterval(() => {
      const timeSinceLastActivity = Date.now() - lastActivityRef.current;
      if (timeSinceLastActivity > 10 * 60 * 1000) { // 10 minutes of inactivity
        if (isActive) endSession();
      } else {
        // If user comes back
        if (user && !isActive) startSession();
      }
    }, 60000);

    return () => {
      events.forEach(event => document.removeEventListener(event, handleActivity, true));
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (sessionTimerRef.current) clearInterval(sessionTimerRef.current);
      void endSession(false);
    };
  }, [isActive, user]);

  return { isActive, startSession, endSession };
} 