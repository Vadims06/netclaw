"""Orchestrates extractor.py (classification) + zoom_channel_client.py
(submission to Border) + panel_feed.py (live status pushes) for every new
transcript/chat entry. Kept separate from rtms_listener.py's SDK callbacks so
each module has one job (Constitution Principle VII: Skill Modularity).
"""

import asyncio
import logging
import time

import extractor
import panel_feed
import zoom_channel_client
from models import registry

logger = logging.getLogger("zoom_rtms.recognition")

# T024: collapse a speech+chat duplicate of the same utterance, within this
# window, into one request rather than two.
_DEDUP_WINDOW_S = 5.0

# meeting_uuid -> (normalized_text, timestamp) of the most recent submitted request
_recent_submissions: dict[str, tuple] = {}


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def on_new_entry(meeting_uuid: str, source: str, text: str):
    """Called synchronously from an RTMS SDK callback; schedules the actual
    (async) recognition work as a task so the SDK callback itself never blocks."""
    asyncio.create_task(_process(meeting_uuid, source, text))


async def _process(meeting_uuid: str, source: str, text: str):
    result = extractor.classify(text)

    if result.kind == "suppressed":
        # FR-009: never even constructs a request. Logged for auditability of
        # the boundary itself, not treated as an event of any kind downstream.
        logger.info("Meeting %s: suppressed (%s): %r", meeting_uuid, result.reason, text)
        return

    if result.kind not in ("investigate", "write_command"):
        return

    # T024: same utterance arriving via both speech and chat within the dedup
    # window collapses to one request.
    normalized = _normalize(text)
    prev = _recent_submissions.get(meeting_uuid)
    if prev and prev[0] == normalized and (time.time() - prev[1]) < _DEDUP_WINDOW_S:
        logger.info("Meeting %s: duplicate of recent request, not resubmitting", meeting_uuid)
        return
    _recent_submissions[meeting_uuid] = (normalized, time.time())

    fields = extractor.extract_fields(text)

    # T022: ambiguous edge case — classified as investigate-worthy but nothing
    # resolvable. Surface plainly rather than guess.
    if result.kind == "investigate" and not (fields.location or fields.technology):
        await panel_feed.push_investigation_result(
            meeting_uuid, request_id="", answer_summary=None, evidence_refs=[])
        session = registry.get(meeting_uuid)
        if session:
            req = session.new_investigation(source=source, raw_text=text,
                                              location=fields.location,
                                              technology=fields.technology,
                                              time_window=fields.time_window)
            req.routing_outcome = "failed_ambiguous"
        logger.info("Meeting %s: ambiguous request, not routed: %r", meeting_uuid, text)
        return

    await panel_feed.push_avatar_state(meeting_uuid, "thinking")
    await panel_feed.push_topic_detected(meeting_uuid, fields.location, fields.technology,
                                          fields.time_window)

    response = await zoom_channel_client.submit_investigation(
        meeting_uuid, source, text, fields.location, fields.technology, fields.time_window)

    if not response.get("accepted"):
        # T023: no registered tooling / Border unreachable — surfaced plainly.
        await panel_feed.push_avatar_state(meeting_uuid, "listening")
        await panel_feed.push_investigation_result(
            meeting_uuid, request_id="", answer_summary=None, evidence_refs=[])
        logger.warning("Meeting %s: investigation not accepted: %s", meeting_uuid,
                       response.get("reason"))
        return

    request_id = response.get("request_id")
    session = registry.get(meeting_uuid)
    if session and request_id in session.investigations:
        pass  # already created by submit path in a fuller implementation
    elif session:
        req = session.new_investigation(source=source, raw_text=text, location=fields.location,
                                          technology=fields.technology,
                                          time_window=fields.time_window)
        session.investigations[request_id] = session.investigations.pop(req.request_id)
        session.investigations[request_id].request_id = request_id

    await panel_feed.push_avatar_state(meeting_uuid, "investigating")


def handle_investigate_result(params: dict):
    """Registered as zoom_channel_client.on_investigate_result. Runs the
    panel-facing side of a Border push (research.md R1/R3)."""
    meeting_uuid = None
    for session in registry.list_active():
        if params.get("request_id") in session.investigations:
            meeting_uuid = session.meeting_uuid
            req = session.investigations[params["request_id"]]
            req.routing_outcome = params.get("routing_outcome")
            req.answer_summary = params.get("answer_summary")
            req.evidence_refs = params.get("evidence_refs", [])
            req.write_action_detected = params.get("write_action_detected", False)
            req.approval_ref = params.get("approval_ref")
            break
    if not meeting_uuid:
        logger.warning("investigate_result for unknown request_id %s", params.get("request_id"))
        return
    asyncio.create_task(panel_feed.push_avatar_state(meeting_uuid, "answered"))
    asyncio.create_task(panel_feed.push_investigation_result(
        meeting_uuid, params.get("request_id"), params.get("answer_summary"),
        params.get("evidence_refs")))
