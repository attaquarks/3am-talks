import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/use-toast';
import { getSupabaseBrowser } from '@/lib/supabaseBrowser';

function apiErrorMessage(body: unknown, fallback: string): string {
  const d = (body as { detail?: string | { message?: string } })?.detail;
  if (typeof d === 'string') return d;
  if (d && typeof d === 'object' && typeof (d as { message?: string }).message === 'string') {
    return (d as { message: string }).message;
  }
  return fallback;
}

function accessTokenFromHash(): string | null {
  let raw = window.location.hash.startsWith('#') ? window.location.hash.slice(1) : window.location.hash;
  // Facebook sometimes appends "#_=_"; only the first fragment is in location.hash for standard OAuth hash tokens
  const idx = raw.indexOf('#');
  if (idx !== -1) raw = raw.slice(0, idx);
  const params = new URLSearchParams(raw);
  return params.get('access_token');
}

export default function OAuthSuccess() {
  const { refetchUser } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    (async () => {
      const search = new URLSearchParams(window.location.search);
      const error = search.get('error');
      const errorDesc = search.get('error_description');
      if (error) {
        // #region agent log
        fetch('http://127.0.0.1:7498/ingest/de8af993-af91-47ad-aef8-03b59e70199a',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'a2dded'},body:JSON.stringify({sessionId:'a2dded',location:'OAuthSuccess.tsx:error_query',message:'oauth error on callback',data:{error,errorDesc},hypothesisId:'verify',runId:'post-fix',timestamp:Date.now()})}).catch(()=>{});
        // #endregion
        toast({
          title: 'Login failed',
          description: decodeURIComponent(errorDesc || error),
          variant: 'destructive',
        });
        navigate('/auth', { replace: true });
        return;
      }

      let accessToken: string | null = null;
      try {
        const supabase = getSupabaseBrowser();
        const {
          data: { session },
        } = await supabase.auth.getSession();
        accessToken = session?.access_token ?? null;
        if (!accessToken) {
          accessToken = accessTokenFromHash();
        }
      } catch (e: any) {
        // #region agent log
        fetch('http://127.0.0.1:7498/ingest/de8af993-af91-47ad-aef8-03b59e70199a',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'a2dded'},body:JSON.stringify({sessionId:'a2dded',location:'OAuthSuccess.tsx:client_err',message:'supabase client or session',data:{err:String(e?.message||e)},hypothesisId:'verify',runId:'post-fix',timestamp:Date.now()})}).catch(()=>{});
        // #endregion
        toast({
          title: 'Login failed',
          description: e?.message ?? 'OAuth configuration error.',
          variant: 'destructive',
        });
        navigate('/auth', { replace: true });
        return;
      }

      if (!accessToken) {
        toast({
          title: 'Login failed',
          description: 'No access token received from OAuth provider.',
          variant: 'destructive',
        });
        navigate('/auth', { replace: true });
        return;
      }

      try {
        let res = await fetch('/api/oauth/session', {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ access_token: accessToken }),
        });
        if (res.status === 404) {
          res = await fetch('/api/auth/oauth/session', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ access_token: accessToken }),
          });
        }

        if (!res.ok) {
          const errBody = await res.json().catch(() => ({}));
          // #region agent log
          fetch('http://127.0.0.1:7498/ingest/de8af993-af91-47ad-aef8-03b59e70199a',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'a2dded'},body:JSON.stringify({sessionId:'a2dded',location:'OAuthSuccess.tsx:session_api',message:'oauth session POST failed',data:{httpStatus:res.status,detailSnippet:JSON.stringify(errBody).slice(0,200)},hypothesisId:'H-404',runId:'not-found',timestamp:Date.now()})}).catch(()=>{});
          // #endregion
          const msg = apiErrorMessage(errBody, 'Session creation failed');
          throw new Error(`HTTP ${res.status}: ${msg}`);
        }

        try {
          const supabase = getSupabaseBrowser();
          await supabase.auth.signOut();
        } catch {
          /* ignore — backend session is canonical */
        }

        await refetchUser();
        navigate('/dashboard', { replace: true });
      } catch (e: any) {
        toast({
          title: 'Login failed',
          description: e.message,
          variant: 'destructive',
        });
        navigate('/auth', { replace: true });
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
    </div>
  );
}
