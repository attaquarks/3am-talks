"""
Edge TTS plugin for LiveKit Agents.

Wraps Microsoft Edge TTS (free, no API key) as a LiveKit TTS provider.
Outputs MP3 audio streamed chunk-by-chunk.
"""

import edge_tts
from livekit.agents import tts, utils, APIConnectOptions, DEFAULT_API_CONNECT_OPTIONS

DEFAULT_VOICE = "en-US-AvaMultilingualNeural"
SAMPLE_RATE = 24000


class TTS(tts.TTS):
    def __init__(self, *, voice: str = DEFAULT_VOICE) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=SAMPLE_RATE,
            num_channels=1,
        )
        self._voice = voice

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> "ChunkedStream":
        return ChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
            voice=self._voice,
        )


class ChunkedStream(tts.ChunkedStream):
    def __init__(
        self,
        *,
        tts: TTS,
        input_text: str,
        conn_options: APIConnectOptions,
        voice: str,
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._voice = voice

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        output_emitter.initialize(
            request_id=utils.shortuuid(),
            sample_rate=SAMPLE_RATE,
            num_channels=1,
            mime_type="audio/mpeg",
        )

        comm = edge_tts.Communicate(self._input_text, self._voice)
        async for chunk in comm.stream():
            if chunk["type"] == "audio" and chunk["data"]:
                output_emitter.push(chunk["data"])

        output_emitter.flush()
