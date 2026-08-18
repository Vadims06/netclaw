"""Per-meeting Zoom RTMS SDK session (research.md R4): consumes transcript,
chat, active-speaker, and screen-share-start/stop signals only — no raw
audio/video (FR-016). Appends entries to the MeetingSession's
LiveContextBuffer and drives connection_state transitions.

Uses Zoom's official RTMS SDK, not a hand-rolled implementation of the RTMS
wire protocol (research.md R4). The SDK (PyPI package "rtms") ships only a
cp313 wheel as of v1.1.0 — this server therefore runs from its own .venv
built with python3.13, not the system python3 (see requirements.txt and
config/openclaw.json's zoom-rtms-mcp entry). The import below still degrades
to a clearly-logged no-op if the SDK is somehow missing at runtime (e.g. the
venv wasn't set up), so the rest of zoom-rtms-mcp (webhook receipt, extractor,
panel feed, MCP tools) still imports and runs without it — but a correctly
set-up install always has it available.
"""

import asyncio
import logging
import time

import recognition
from models import ContentEntry, SpeakerChangeEntry, TranscriptEntry, registry

logger = logging.getLogger("zoom_rtms.listener")

try:
    import rtms as _rtms_sdk  # Zoom's official RTMS Python SDK (package name per Zoom's distribution)
    _SDK_AVAILABLE = True
except ImportError:
    _rtms_sdk = None
    _SDK_AVAILABLE = False
    logger.warning(
        "Zoom RTMS SDK not installed — rtms_listener will not receive live "
        "meeting signals. See requirements.txt. All other zoom-rtms-mcp "
        "functionality is unaffected."
    )

_active_listeners: dict[str, "MeetingRtmsListener"] = {}


class MeetingRtmsListener:
    """Wraps one RTMS SDK session for one meeting_uuid."""

    def __init__(self, meeting_uuid: str, payload: dict):
        self.meeting_uuid = meeting_uuid
        self.payload = payload
        self._sdk_session = None
        self._task: asyncio.Task | None = None

    async def start(self):
        session = registry.get(self.meeting_uuid)
        if not session:
            logger.warning("start() called for unknown meeting %s", self.meeting_uuid)
            return
        if not _SDK_AVAILABLE:
            # Degraded mode: session exists (created by webhook.py), but no
            # live signals will ever arrive. connection_state reflects this
            # honestly rather than pretending to be "live".
            session.connection_state = "degraded"
            logger.warning(
                "Meeting %s: RTMS SDK unavailable, listener running in degraded "
                "(no-op) mode", self.meeting_uuid)
            return
        try:
            self._sdk_session = await _rtms_sdk.connect(
                meeting_uuid=self.meeting_uuid,
                server_urls=self.payload.get("server_urls"),
                on_transcript=self._on_transcript,
                on_chat=self._on_chat,
                on_speaker_change=self._on_speaker_change,
                on_content=self._on_content,
                on_disconnect=self._on_disconnect,
            )
            session.connection_state = "live"
            logger.info("Meeting %s: RTMS session live", self.meeting_uuid)
        except Exception as e:
            session.connection_state = "degraded"
            logger.error("Meeting %s: RTMS connect failed: %s", self.meeting_uuid, e)

    async def stop(self):
        if self._sdk_session:
            try:
                await self._sdk_session.close()
            except Exception:
                pass
        _active_listeners.pop(self.meeting_uuid, None)

    # ---- SDK callbacks (shape is illustrative — pinned to the real SDK's
    # actual callback signatures once installed; the LiveContextBuffer entry
    # shapes below are authoritative per data-model.md regardless) ---------

    def _session(self):
        return registry.get(self.meeting_uuid)

    def _on_transcript(self, participant_id: str, participant_name: str, text: str):
        s = self._session()
        if s:
            s.buffer.append(TranscriptEntry(time.time(), participant_id, participant_name,
                                             text, kind="transcript"))
            recognition.on_new_entry(self.meeting_uuid, "speech", text)

    def _on_chat(self, participant_id: str, participant_name: str, text: str):
        s = self._session()
        if s:
            s.buffer.append(TranscriptEntry(time.time(), participant_id, participant_name,
                                             text, kind="chat"))
            recognition.on_new_entry(self.meeting_uuid, "chat", text)

    def _on_speaker_change(self, participant_id: str):
        s = self._session()
        if s:
            s.buffer.append(SpeakerChangeEntry(time.time(), participant_id))

    def _on_content(self, kind: str, participant_id: str):
        s = self._session()
        if s:
            s.buffer.append(ContentEntry(time.time(), kind, participant_id))

    def _on_disconnect(self, reason: str = ""):
        s = self._session()
        if s:
            s.connection_state = "degraded"
            logger.warning("Meeting %s: RTMS disconnected (%s)", self.meeting_uuid, reason)


async def start_listener(meeting_uuid: str, payload: dict):
    listener = MeetingRtmsListener(meeting_uuid, payload)
    _active_listeners[meeting_uuid] = listener
    await listener.start()


async def stop_listener(meeting_uuid: str):
    listener = _active_listeners.get(meeting_uuid)
    if listener:
        await listener.stop()
