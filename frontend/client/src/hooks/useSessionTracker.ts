import { useEffect, useState, useRef } from 'react';
import { supabase } from '@/integrations/supabase/client';

export function useSessionTracker() {
  const [isActive, setIsActive] = useState(false);
  const sessionStartRef = useRef<number | null>(null);
  const lastActivityRef = useRef<number>(Date.now());
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const inactivityRef = useRef<NodeJS.Timeout | null>(null);
  const sessionTimerRef = useRef<NodeJS.Timeout | null>(null);
  const dailyLoginRecordedRef = useRef<string | null>(null);

  const startSession = async () => {
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
          sessionStartRef.current = Date.now(); // Reset timer
        }
      }
    }, 60000); // Update every minute
  };

  const endSession = async () => {
    if (!isActive || !sessionStartRef.current) return;

    const sessionDuration = Math.floor((Date.now() - sessionStartRef.current) / 1000 / 60);
    
    if (sessionDuration > 0) {
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
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      const today = new Date().toISOString().split('T')[0];
      
      // Check if we already recorded today's login
      if (dailyLoginRecordedRef.current === today) {
        console.log(`Daily login already recorded for ${today}`);
        return;
      }
      
      // Reset daily login tracking if date has changed
      if (dailyLoginRecordedRef.current && dailyLoginRecordedRef.current !== today) {
        console.log(`Date changed from ${dailyLoginRecordedRef.current} to ${today}, resetting daily login tracking`);
      }
      
      console.log(`Recording daily login for user ${user.id} on ${today}`);
      
      // Update last_session_date to today's date and update streak
      await supabase
        .from('user_stats')
        .update({ 
          last_session_date: today
        })
        .eq('user_id', user.id);

      // Update streak based on last_session_date
      await updateStreak();
      
      // Mark today's login as recorded
      dailyLoginRecordedRef.current = today;
    } catch (error) {
      console.error('Error recording daily login:', error);
    }
  };

  const updateStreak = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // Get current user stats
      const { data: userStats } = await supabase
        .from('user_stats')
        .select('last_session_date, current_streak')
        .eq('user_id', user.id)
        .single();

      if (!userStats) return;

      const today = new Date().toISOString().split('T')[0];
      const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString().split('T')[0];
      
      // If last_session_date is today, don't update streak (already logged in today)
      if (userStats.last_session_date === today) {
        console.log(`Already logged in today (${today}), keeping streak at ${userStats.current_streak}`);
        return;
      }
      
      // If last_session_date is yesterday, increment streak
      if (userStats.last_session_date === yesterday) {
        const newStreak = userStats.current_streak + 1;
        console.log(`Continuing streak: ${newStreak} (last login: ${userStats.last_session_date}, today: ${today})`);
        
        await supabase
          .from('user_stats')
          .update({ current_streak: newStreak })
          .eq('user_id', user.id);
      } else {
        // If last_session_date is before yesterday, reset to 1
        console.log(`Resetting streak to 1 (last login: ${userStats.last_session_date}, today: ${today})`);
        
        await supabase
          .from('user_stats')
          .update({ current_streak: 1 })
          .eq('user_id', user.id);
      }

    } catch (error) {
      console.error('Error updating streak:', error);
    }
  };

  const updateSessionTime = async (minutes: number) => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user || minutes <= 0) return;

      // Get current total_minutes first
      const { data: currentStats } = await supabase
        .from('user_stats')
        .select('total_minutes')
        .eq('user_id', user.id)
        .single();

      const currentTotalMinutes = currentStats?.total_minutes || 0;
      const newTotalMinutes = currentTotalMinutes + minutes;

      // Update total minutes in user_stats
      const { error } = await supabase
        .from('user_stats')
        .update({ 
          total_minutes: newTotalMinutes,
          last_session_date: new Date().toISOString().split('T')[0]
        })
        .eq('user_id', user.id);

      if (error) {
        console.error('Error updating session time:', error);
      }
    } catch (error) {
      console.error('Error updating session time:', error);
    }
  };

  // Listen for auth state changes
  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        if (event === 'SIGNED_OUT') {
          endSession();
          // Reset daily login tracking on logout
          dailyLoginRecordedRef.current = null;
        } else if (event === 'SIGNED_IN' && session) {
          startSession();
        }
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    const handleActivity = () => updateActivity();
    
    const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
    events.forEach(event => document.addEventListener(event, handleActivity, true));

    // Only start session if user is authenticated
    const checkAndStartSession = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (user) {
        startSession();
      }
    };
    
    checkAndStartSession();

    // Check for inactivity every minute
    intervalRef.current = setInterval(() => {
      const timeSinceLastActivity = Date.now() - lastActivityRef.current;
      if (timeSinceLastActivity > 10 * 60 * 1000) { // 10 minutes of inactivity
        endSession();
      }
    }, 60000);

    return () => {
      events.forEach(event => document.removeEventListener(event, handleActivity, true));
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (sessionTimerRef.current) clearInterval(sessionTimerRef.current);
      endSession();
    };
  }, []);

  return { isActive, startSession, endSession };
} 