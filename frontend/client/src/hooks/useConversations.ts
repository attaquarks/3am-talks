import { useEffect, useState } from 'react';
import { useToast } from '@/hooks/use-toast';

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

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    fetchConversations();
  }, []);

  const fetchConversations = async () => {
    try {
      const response = await fetch('/api/data/conversations');
      if (!response.ok) {
        if (response.status === 401) return;
        throw new Error('Failed to fetch conversations');
      }

      const data = await response.json();
      setConversations(data || []);
    } catch (error) {
      console.error('Error fetching conversations:', error);
      // Fail silently on auth
    } finally {
      setLoading(false);
    }
  };

  const createConversation = async (conversation: Omit<Conversation, 'id' | 'created_at' | 'updated_at'>) => {
    try {
      const response = await fetch('/api/data/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(conversation)
      });

      if (!response.ok) {
        throw new Error('Failed to create conversation');
      }

      const data = await response.json();

      setConversations(prev => [data, ...prev]);
      toast({
        title: "Success",
        description: "Conversation created successfully.",
      });
      return data;
    } catch (error) {
      console.error('Error creating conversation:', error);
      toast({
        title: "Error",
        description: "Failed to create conversation.",
        variant: "destructive",
      });
      return null;
    }
  };

  return { conversations, loading, createConversation, refetch: fetchConversations };
}