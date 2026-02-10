import { useCallback } from "react";
import "@livekit/components-styles";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
  useLocalParticipant,
  BarVisualizer,
  DisconnectButton,
} from "@livekit/components-react";
import { Phone, PhoneOff, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useVoiceCall } from "@/hooks/useVoiceCall";

// ---------------------------------------------------------------------------
// Inner component — must be rendered inside <LiveKitRoom>
// ---------------------------------------------------------------------------

function VoiceAssistantVisualizer() {
  const { state, audioTrack } = useVoiceAssistant();
  const { microphoneTrack } = useLocalParticipant();

  const trackToVisualize = state === "speaking" ? audioTrack : microphoneTrack;

  const stateLabel: Record<string, string> = {
    connecting: "Connecting…",
    listening: "Listening…",
    thinking: "Thinking…",
    speaking: "Ella is speaking…",
  };

  return (
    <div className="flex flex-col items-center justify-center gap-4">
      <div className="h-32 w-full max-w-xs">
        <BarVisualizer
          state={state}
          barCount={5}
          trackRef={trackToVisualize}
          className="h-full w-full"
        />
      </div>
      <p className="text-sm text-muted-foreground animate-pulse">
        {stateLabel[state] ?? state}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component — voice call modal / overlay
// ---------------------------------------------------------------------------

interface VoiceCallProps {
  className?: string;
}

export default function VoiceCall({ className }: VoiceCallProps) {
  const { connectionDetails, isConnecting, error, connect, disconnect } =
    useVoiceCall();

  const handleDisconnect = useCallback(() => {
    disconnect();
  }, [disconnect]);

  // ── Not connected: show "Talk to Ella" button ─────────────────────────
  if (!connectionDetails) {
    return (
      <div className={cn("flex flex-col items-center gap-2", className)}>
        <Button
          onClick={connect}
          disabled={isConnecting}
          variant="outline"
          size="sm"
          className="gap-2 transition-all duration-200"
        >
          {isConnecting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Phone className="h-4 w-4" />
          )}
          {isConnecting ? "Connecting…" : "Talk to Ella"}
        </Button>

        {error && (
          <div className="flex items-center gap-1 text-xs text-destructive">
            <AlertCircle className="h-3 w-3" />
            <span>{error}</span>
          </div>
        )}
      </div>
    );
  }

  // ── Connected: show voice call overlay ────────────────────────────────
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div className="relative w-full max-w-sm rounded-2xl border border-border/50 bg-card p-8 shadow-2xl">
        {/* Header */}
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-r from-primary to-primary/70">
            <Phone className="h-8 w-8 text-primary-foreground" />
          </div>
          <h2 className="text-lg font-semibold text-foreground">
            Voice Session with Ella
          </h2>
          <p className="text-xs text-muted-foreground">
            Speak naturally — Ella is listening
          </p>
        </div>

        {/* LiveKit Room */}
        <LiveKitRoom
          audio={true}
          video={false}
          token={connectionDetails.participantToken}
          serverUrl={connectionDetails.serverUrl}
          connect={true}
          onDisconnected={handleDisconnect}
          className="flex flex-col items-center gap-6"
        >
          <RoomAudioRenderer />
          <VoiceAssistantVisualizer />

          {/* End call button */}
          <DisconnectButton className="inline-flex items-center justify-center gap-2 rounded-full bg-destructive px-6 py-3 text-sm font-medium text-destructive-foreground shadow-lg transition-all hover:bg-destructive/90 hover:shadow-xl">
            <PhoneOff className="h-4 w-4" />
            End Call
          </DisconnectButton>
        </LiveKitRoom>
      </div>
    </div>
  );
}
