import { useCallback, useEffect, useState } from "react";
import "@livekit/components-styles";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
  useLocalParticipant,
  useDataChannel,
  BarVisualizer,
  DisconnectButton,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import {
  Phone,
  PhoneOff,
  Loader2,
  AlertCircle,
  Mic,
  MicOff,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useVoiceCall } from "@/hooks/useVoiceCall";
import { CrisisCountdownModal } from "@/components/CrisisCountdownModal";

// ---------------------------------------------------------------------------
// Inner component — must be rendered inside <LiveKitRoom>
// ---------------------------------------------------------------------------

// Bridges the LiveKit data channel into React state. Mounted inside
// <LiveKitRoom> so it can use the room context hooks.
interface VoiceDataBridgeProps {
  onCrisisCountdown: (seconds: number) => void;
  onAgentState?: (state: string) => void;
}

function VoiceDataBridge({ onCrisisCountdown, onAgentState }: VoiceDataBridgeProps) {
  useDataChannel((msg) => {
    try {
      const text = new TextDecoder().decode(msg.payload);
      const payload = JSON.parse(text);
      if (payload?.type === "crisis.countdown.start") {
        const seconds = payload?.countdown?.seconds ?? 30;
        onCrisisCountdown(typeof seconds === "number" ? seconds : 30);
      } else if (payload?.type === "agent.state.change" && onAgentState) {
        if (typeof payload.state === "string") onAgentState(payload.state);
      }
    } catch {
      // Non-JSON or unexpected payload — ignore.
    }
  });
  return null;
}

function VoiceAssistantVisualizer({
  agentState,
  isMuted,
}: {
  agentState?: string;
  isMuted: boolean;
}) {
  const { state, audioTrack } = useVoiceAssistant();
  const { microphoneTrack, localParticipant } = useLocalParticipant();

  const trackToVisualize =
    state === "speaking"
      ? audioTrack
      : microphoneTrack
      ? {
          participant: localParticipant,
          publication: microphoneTrack,
          source: Track.Source.Microphone,
        }
      : undefined;

  const stateLabel: Record<string, string> = {
    connecting: "Connecting…",
    listening: "Listening…",
    thinking: "Thinking…",
    generating: "Composing a reply…",
    speaking: "Ella is speaking…",
    interrupted: "Interrupted — go ahead",
  };

  // Prefer the agent's own published state (from backend) when present —
  // it distinguishes "thinking" from "generating" from "speaking" more
  // precisely than LiveKit's derived state. When the user has muted their
  // mic, override the label so the visual matches what Ella can hear.
  const effective = agentState ?? state;
  const displayLabel = isMuted
    ? "Microphone muted — Ella cannot hear you"
    : stateLabel[effective] ?? effective;

  return (
    <div className="flex flex-col items-center justify-center gap-4">
      <div
        className={cn(
          "h-32 w-full max-w-xs transition-opacity duration-200",
          isMuted && state !== "speaking" && "opacity-30",
        )}
      >
        {trackToVisualize && (
          <BarVisualizer
            state={state}
            barCount={5}
            track={trackToVisualize}
            className="h-full w-full"
          />
        )}
      </div>
      <p
        className={cn(
          "text-sm text-muted-foreground",
          !isMuted && "animate-pulse",
        )}
      >
        {displayLabel}
      </p>
    </div>
  );
}

// Mute toggle. The button reads its truth from the LiveKit microphone
// track publication so external mute events (browser permission revoked,
// hardware mute) stay in sync. On toggle it (1) flips the track via the
// LiveKit SDK so no audio leaves the browser when muted, and (2) publishes
// a `voice.mute.state` event on the data channel so the backend agent can
// log/track the state. The data publish is best-effort — local mute is the
// authoritative behavior.
function MuteToggleButton({
  onMuteChange,
}: {
  onMuteChange: (muted: boolean) => void;
}) {
  const { localParticipant, microphoneTrack } = useLocalParticipant();
  const [pending, setPending] = useState(false);

  const isMuted = microphoneTrack?.isMuted ?? false;

  useEffect(() => {
    onMuteChange(isMuted);
  }, [isMuted, onMuteChange]);

  const handleToggle = useCallback(async () => {
    if (!localParticipant || pending) return;
    setPending(true);
    const next = !isMuted;
    try {
      await localParticipant.setMicrophoneEnabled(!next);

      try {
        const payload = JSON.stringify({
          type: "voice.mute.state",
          muted: next,
          ts: Date.now() / 1000,
        });
        await localParticipant.publishData(
          new TextEncoder().encode(payload),
          { reliable: true, topic: "voice.control" },
        );
      } catch {
        // Data publish is best-effort telemetry; the local mute already took effect.
      }
    } catch (err) {
      console.error("[VoiceCall] Failed to toggle mute:", err);
    } finally {
      setPending(false);
    }
  }, [localParticipant, isMuted, pending]);

  return (
    <Button
      type="button"
      onClick={handleToggle}
      disabled={pending || !localParticipant}
      variant={isMuted ? "destructive" : "secondary"}
      className={cn(
        "inline-flex h-12 w-12 items-center justify-center rounded-full p-0 shadow-lg transition-all hover:shadow-xl",
        isMuted && "ring-2 ring-destructive/40",
      )}
      title={isMuted ? "Unmute microphone" : "Mute microphone"}
      aria-label={isMuted ? "Unmute microphone" : "Mute microphone"}
      aria-pressed={isMuted}
    >
      {isMuted ? (
        <MicOff className="h-5 w-5" />
      ) : (
        <Mic className="h-5 w-5" />
      )}
    </Button>
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
  const [crisisState, setCrisisState] = useState<{ open: boolean; seconds: number }>({
    open: false,
    seconds: 30,
  });
  const [agentState, setAgentState] = useState<string | undefined>(undefined);
  const [isMuted, setIsMuted] = useState(false);

  const handleDisconnect = useCallback(() => {
    setAgentState(undefined);
    setIsMuted(false);
    void disconnect();
  }, [disconnect]);

  const handleCrisisCountdown = useCallback((seconds: number) => {
    setCrisisState({ open: true, seconds });
  }, []);

  const closeCrisisModal = useCallback(() => {
    setCrisisState((s) => ({ ...s, open: false }));
  }, []);

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
          <VoiceDataBridge
            onCrisisCountdown={handleCrisisCountdown}
            onAgentState={setAgentState}
          />
          <VoiceAssistantVisualizer agentState={agentState} isMuted={isMuted} />

          {/* Call controls: mute toggle + end call */}
          <div className="flex items-center justify-center gap-4">
            <MuteToggleButton onMuteChange={setIsMuted} />
            <DisconnectButton className="inline-flex items-center justify-center gap-2 rounded-full bg-destructive px-6 py-3 text-sm font-medium text-destructive-foreground shadow-lg transition-all hover:bg-destructive/90 hover:shadow-xl">
              <PhoneOff className="h-4 w-4" />
              End Call
            </DisconnectButton>
          </div>
        </LiveKitRoom>
      </div>

      <CrisisCountdownModal
        open={crisisState.open}
        seconds={crisisState.seconds}
        onClose={closeCrisisModal}
      />
    </div>
  );
}
