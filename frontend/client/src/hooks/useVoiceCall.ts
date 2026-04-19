import { useState, useCallback } from "react";

interface ConnectionDetails {
  serverUrl: string;
  roomName: string;
  participantName: string;
  participantToken: string;
}

interface UseVoiceCallReturn {
  connectionDetails: ConnectionDetails | null;
  isConnecting: boolean;
  error: string | null;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
}

/**
 * Hook to manage LiveKit voice call connection lifecycle.
 * Fetches a token from the backend and provides connection details
 * for the LiveKitRoom component.
 */
export function useVoiceCall(): UseVoiceCallReturn {
  const [connectionDetails, setConnectionDetails] =
    useState<ConnectionDetails | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connect = useCallback(async () => {
    setIsConnecting(true);
    setError(null);

    try {
      const response = await fetch("/api/livekit/token", {
        method: "POST",
        credentials: "include",
      });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Server error: ${response.status}`);
      }

      const details: ConnectionDetails = await response.json();
      setConnectionDetails(details);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to start voice session";
      setError(message);
      setConnectionDetails(null);
    } finally {
      setIsConnecting(false);
    }
  }, []);

  const disconnect = useCallback(async () => {
    try {
      await fetch("/api/session/flush", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        credentials: "include",
      });
    } catch {
      // Best-effort flush; UI disconnect should continue even if flush fails.
    }
    setConnectionDetails(null);
    setError(null);
  }, []);

  return { connectionDetails, isConnecting, error, connect, disconnect };
}
