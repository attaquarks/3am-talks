import { useEffect, useState } from 'react';
import { useToast } from '@/hooks/use-toast';

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
      const response = await fetch('/api/data/mood_entries');
      if (!response.ok) {
        if (response.status === 401) return;
        throw new Error('Failed to fetch mood entries');
      }

      const data = await response.json();
      setMoodEntries(data || []);
    } catch (error) {
      console.error('Error fetching mood entries:', error);
      // Fail silently on auth
    } finally {
      setLoading(false);
    }
  };

  const createMoodEntry = async (entry: Omit<MoodEntry, 'id' | 'user_id' | 'created_at' | 'updated_at'>) => {
    try {
      const response = await fetch('/api/data/mood_entries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entry)
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to create mood entry');
      }

      const data = await response.json();

      setMoodEntries(prev => [data, ...prev]);
      toast({
        title: "Success",
        description: "Mood entry created successfully.",
      });
      return data;
    } catch (error: any) {
      console.error('Error creating mood entry:', error);
      toast({
        title: "Error",
        description: error.message || "Failed to create mood entry.",
        variant: "destructive",
      });
      return null;
    }
  };

  return { moodEntries, loading, createMoodEntry, refetch: fetchMoodEntries };
}