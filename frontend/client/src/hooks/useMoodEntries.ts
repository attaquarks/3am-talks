import { useEffect, useState } from 'react';
import { useToast } from '@/hooks/use-toast';
import { supabase } from '@/integrations/supabase/client';

interface MoodEntry {
  id: string;
  user_id: string;
  date: string;
  mood: string;
  note: string | null;
  prompt: string | null;
  prompt_answer: string | null;
  created_at: string;
  updated_at: string;
}

export function useMoodEntries() {
  const [moodEntries, setMoodEntries] = useState<MoodEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    fetchMoodEntries();
  }, []);

  const fetchMoodEntries = async () => {
    try {
      const { data, error } = await supabase
        .from('mood_entries')
        .select('*')
        .order('date', { ascending: false });

      if (error) throw error;
      setMoodEntries(data || []);
    } catch (error) {
      console.error('Error fetching mood entries:', error);
      toast({
        title: "Error",
        description: "Failed to fetch mood entries.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const createMoodEntry = async (entry: Omit<MoodEntry, 'id' | 'user_id' | 'created_at' | 'updated_at'>) => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error('Not authenticated');

      const { data, error } = await supabase
        .from('mood_entries')
        .upsert([{ ...entry, user_id: user.id }], { 
          onConflict: 'user_id,date',
          ignoreDuplicates: false 
        })
        .select()
        .single();

      if (error) throw error;
      
      setMoodEntries(prev => [data, ...prev]);
      toast({
        title: "Success",
        description: "Mood entry created successfully.",
      });
      return data;
    } catch (error) {
      console.error('Error creating mood entry:', error);
      toast({
        title: "Error",
        description: "Failed to create mood entry.",
        variant: "destructive",
      });
      return null;
    }
  };

  return { moodEntries, loading, createMoodEntry, refetch: fetchMoodEntries };
}