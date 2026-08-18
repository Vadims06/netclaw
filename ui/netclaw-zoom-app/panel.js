/**
 * NetClaw Zoom App side panel (spec 118, tasks T021/T034/T035/T036/T037).
 * Connects to zoom-rtms-mcp's panel_feed WebSocket
 * (contracts/zoom-app-panel-feed.md), renders avatar/status/results, wires
 * Collaborate Mode + Guest Mode (US3), and offers the camera-overlay toggle
 * (US5, delegates the actual Layers API call to overlay.js).
 */

const AVATAR_ICONS = {
  listening: "🦞", thinking: "🤔", investigating: "🔍", answered: "✅",
};

let meetingUuid = null;
let participantId = null;
let ws = null;
let overlayEnabled = false;

const avatarEl = document.getElementById("avatar");
const statusEl = document.getElementById("status");
const topicEl = document.getElementById("topic");
const resultEl = document.getElementById("result");
const overlayBtn = document.getElementById("overlay-toggle");

function connect() {
  // Same-origin as the Home URL that served this panel (contracts: the
  // panel_feed server and the webhook/OAuth server share a host in this
  // feature's design, research.md R3).
  const wsUrl = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/";
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    statusEl.textContent = "Listening";
    if (meetingUuid && participantId) sendViewerJoined();
  };
  ws.onclose = () => {
    statusEl.textContent = "Disconnected — retrying…";
    statusEl.className = "degraded";
    setTimeout(connect, 3000);
  };
  ws.onerror = () => { /* onclose will fire and retry */ };
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    handleServerMessage(msg);
  };
}

function sendViewerJoined() {
  send({ type: "viewer_joined", meeting_uuid: meetingUuid, participant_id: participantId });
}

function send(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
}

function handleServerMessage(msg) {
  if (msg.meeting_uuid && msg.meeting_uuid !== meetingUuid) return;

  switch (msg.type) {
    case "avatar_state":
      avatarEl.textContent = AVATAR_ICONS[msg.state] || "🦞";
      statusEl.textContent = msg.state.charAt(0).toUpperCase() + msg.state.slice(1);
      statusEl.className = "";
      if (window.NetClawOverlay) window.NetClawOverlay.setState(msg.state);
      break;
    case "topic_detected":
      topicEl.style.display = "block";
      topicEl.textContent = [
        msg.location ? `Location: ${msg.location}` : null,
        msg.technology ? `Technology: ${msg.technology}` : null,
        msg.time_window ? `Time window: ${msg.time_window}` : null,
      ].filter(Boolean).join(" · ") || "Investigating detected topic…";
      break;
    case "investigation_result":
      resultEl.style.display = "block";
      resultEl.textContent = msg.answer_summary || "Could not complete this investigation.";
      break;
    case "connection_state":
      if (msg.state === "degraded") {
        statusEl.textContent = "Connection degraded";
        statusEl.className = "degraded";
      } else if (msg.state === "connecting") {
        statusEl.textContent = "Connecting…";
        statusEl.className = "connecting";
      }
      break;
  }
}

overlayBtn.addEventListener("click", async () => {
  overlayEnabled = !overlayEnabled;
  overlayBtn.textContent = overlayEnabled ? "Disable camera overlay" : "Enable camera overlay";
  overlayBtn.className = overlayEnabled ? "enabled" : "";
  send({
    type: overlayEnabled ? "camera_overlay_enable" : "camera_overlay_disable",
    meeting_uuid: meetingUuid, participant_id: participantId,
  });
  if (window.NetClawOverlay) {
    if (overlayEnabled) await window.NetClawOverlay.enable();
    else await window.NetClawOverlay.disable();
  }
});

// ---- Zoom Apps SDK: Collaborate Mode + Guest Mode (US3) --------------------

async function initZoomSdk() {
  if (typeof zoomSdk === "undefined") {
    // Not running inside the Zoom client (e.g. local dev) — fall back to a
    // query-string meeting_uuid so the panel is still testable standalone.
    const params = new URLSearchParams(location.search);
    meetingUuid = params.get("meeting_uuid") || "dev-meeting";
    participantId = params.get("participant_id") || "dev-participant";
    connect();
    return;
  }

  await zoomSdk.config({
    capabilities: [
      "getRunningContext", "getMeetingContext", "getUserContext",
      "onMeeting", "startCollaborate", "joinCollaborate", "leaveCollaborate",
      "onCollaborateChange",
    ],
  });

  const meetingContext = await zoomSdk.getMeetingContext();
  meetingUuid = meetingContext.meetingUUID;

  const userContext = await zoomSdk.getUserContext();
  // Guest Mode (FR-012): an unauthenticated participant still has a
  // per-session participantId even without a Zoom login — treated
  // identically to an authenticated one by this panel and by panel_feed.py.
  participantId = userContext.participantId || userContext.screenName || "guest";

  zoomSdk.onCollaborateChange((event) => {
    // Collaborate Mode (US3): every collaborator renders the same
    // meeting_uuid-scoped state via the shared panel_feed connection —
    // nothing extra needed here beyond making sure this connection is live.
    if (event.collaborateUUID && !ws) connect();
  });

  connect();
}

initZoomSdk();
