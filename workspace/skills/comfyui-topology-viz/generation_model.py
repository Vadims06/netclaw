"""
NEW entities for the ComfyUI network topology visualization skill — not ported from spec 046,
since 046 has no equivalent of a generation job, a model-availability check, or a generated image.
See specs/120-comfyui-topology-viz/data-model.md.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from topology_model import SourceKind


class GenerationStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    FAILED = "failed"


class ModelCheckStatus(str, Enum):
    OK = "ok"
    BACKEND_UNREACHABLE = "backend_unreachable"
    NO_USABLE_MODEL = "no_usable_model"


class FailureKind(str, Enum):
    """The six distinct, distinguishable failure conditions this feature can report
    (data-model.md's Generation Failure taxonomy). Each maps to exactly one spec FR."""

    BACKEND_UNREACHABLE = "backend_unreachable"  # FR-007
    NO_USABLE_MODEL = "no_usable_model"  # FR-008
    GENERATION_JOB_FAILED = "generation_job_failed"  # FR-009
    GENERATION_ALREADY_IN_PROGRESS = "generation_already_in_progress"  # FR-009a
    SOURCE_UNREACHABLE = "source_unreachable"  # FR-012
    EMPTY_TOPOLOGY = "empty_topology"  # FR-013


class GenerationFailure(Exception):
    """Raised by generation.py with one of the six FailureKind values and a
    human-readable, distinguishable message (SC-003)."""

    def __init__(self, kind: FailureKind, message: str):
        self.kind = kind
        self.message = message
        super().__init__(message)


@dataclass
class ModelAvailabilityCheck:
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    available_checkpoints: list[str] = field(default_factory=list)
    selected_checkpoint: Optional[str] = None
    status: ModelCheckStatus = ModelCheckStatus.NO_USABLE_MODEL


@dataclass
class GenerationRequest:
    request_id: str
    snapshot_source: SourceKind
    prompt_text: str = ""
    model_used: Optional[str] = None
    template_id: Optional[str] = None
    workflow: Optional[dict] = None
    comfyui_task_id: Optional[str] = None
    status: GenerationStatus = GenerationStatus.PENDING
    submitted_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


@dataclass
class GeneratedImage:
    file_path: str
    generation_request_id: str
    model_used: str
    snapshot_source: SourceKind
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
