import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';

interface AuthWrapperProps {
  children: React.ReactNode;
}

export function AuthWrapper({ children }: AuthWrapperProps) {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (loading) return;

    const publicPaths = ['/', '/auth', '/auth/therapist', '/learn-more', '/auth/oauth-success', '/invite/accept', '/about'];
    const isPublicPath = publicPaths.includes(location.pathname);
    const role = user?.role ?? 'patient';
    const status = user?.account_status ?? 'active';

    if (!user && !isPublicPath) {
      navigate('/auth');
      return;
    }

    if (!user) return;

    // Therapists awaiting verification — allow only pending page + profile + auth.
    if (role === 'therapist' && status === 'pending_verification') {
      const allowed = ['/therapist-portal/pending', '/therapist-portal/profile', '/auth', '/'];
      if (!allowed.includes(location.pathname)) {
        navigate('/therapist-portal/pending');
      }
      return;
    }

    if (status !== 'active') {
      navigate('/auth');
      return;
    }

    if (location.pathname === '/' || location.pathname === '/auth' || location.pathname === '/auth/therapist') {
      if (role === 'admin') navigate('/admin');
      else if (role === 'therapist') navigate('/therapist-portal');
      else navigate('/dashboard');
      return;
    }

    if (location.pathname.startsWith('/admin') && role !== 'admin') {
      navigate(role === 'therapist' ? '/therapist-portal' : '/dashboard');
      return;
    }

    if (location.pathname.startsWith('/therapist-portal') && role !== 'therapist') {
      navigate(role === 'admin' ? '/admin' : '/dashboard');
      return;
    }

    const patientOnlyPaths = ['/dashboard', '/chat', '/therapist', '/history', '/profile', '/my-therapists'];
    const onPatientPath = patientOnlyPaths.some(
      (p) => location.pathname === p || location.pathname.startsWith(p + '/'),
    );
    if (role === 'admin' && onPatientPath) {
      navigate('/admin');
      return;
    }
    if (role === 'therapist' && onPatientPath) {
      navigate('/therapist-portal');
      return;
    }
  }, [user, loading, navigate, location.pathname]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return <>{children}</>;
}
