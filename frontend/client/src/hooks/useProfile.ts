import { useEffect, useState } from 'react';
import { useToast } from '@/hooks/use-toast';

interface Profile {
  id: string;
  user_id: string;
  name: string;
  mood_preference: string;
  emergency_contact?: string;
  phone?: string;
  deleted?: boolean;
  created_at: string;
  updated_at: string;
}

export function useProfile() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    try {
      const response = await fetch('/api/data/profiles');
      if (!response.ok) {
        if (response.status === 401) {
          // Not authenticated, just return (AuthWrapper handles redirect if needed)
          return;
        }
        throw new Error('Failed to fetch profile');
      }

      const data = await response.json();

      // If no profile found or profile is deleted (shouldn't happen with our API logic usually)
      if (data.deleted) {
        // Handle deletion logic if needed, or just warn
        toast({
          title: "Account Deleted",
          description: "Your account has been deleted.",
        });
        return;
      }

      setProfile(data);
    } catch (error) {
      console.error('Error fetching profile:', error);
      // Fail silently on 401/auth errors to avoid spamming toasts during initial load
    } finally {
      setLoading(false);
    }
  };

  const updateProfile = async (updates: Partial<Pick<Profile, 'name' | 'mood_preference' | 'emergency_contact' | 'phone'>>) => {
    try {
      const response = await fetch('/api/data/profiles', {
        method: 'POST', // Using POST for creation/update as per api.py
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(updates)
      });

      if (!response.ok) throw new Error('Failed to update profile');

      const data = await response.json();
      setProfile(data);
      toast({
        title: "Success",
        description: "Profile updated successfully.",
      });
    } catch (error) {
      console.error('Error updating profile:', error);
      toast({
        title: "Error",
        description: "Failed to update profile.",
        variant: "destructive",
      });
    }
  };

  return { profile, loading, updateProfile, refetch: fetchProfile };
}