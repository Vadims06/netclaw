"""
Unit test for spec 122 FR-009/SC-004 (finding D1's collapsed Phase 5): DECORATIVE_LABEL must be
referenced in both the free-preview workflow and the generate/status-check workflow documented in
SKILL.md, so a completed generation — the case most likely to be mistaken for an accurate diagram
— is never presented without it.

Unlike test_fantastical_prompt_builder.py and test_worldlabs_marble_mcp.py, there is no Python
function that composes the final human-facing chat response — that composition happens
conversationally, following SKILL.md's documented workflow (the agent, not this repo's code, writes
the final message). So this test verifies the one thing that actually is checkable: that the
constant is required by name in both workflow sections of the documentation the agent follows,
including the completed-generation and get_world-fallback cases specifically (not just the
in-progress/failure cases, where an operator is least likely to be misled).
"""

from pathlib import Path

_skill_path = Path(__file__).parent.parent.parent / "workspace" / "skills" / "worldlabs-topology-viz" / "SKILL.md"


def _section(markdown: str, heading: str) -> str:
    """Return the text of one '## Workflow: ...' section, up to the next '## ' heading."""
    start = markdown.index(heading)
    rest = markdown[start + len(heading):]
    next_heading = rest.find("\n## ")
    return rest if next_heading == -1 else rest[:next_heading]


def test_decorative_label_is_present_in_the_preview_workflow():
    markdown = _skill_path.read_text()
    section = _section(markdown, "## Workflow: Free Preview")
    assert "DECORATIVE_LABEL" in section


def test_decorative_label_is_present_in_the_generate_workflow():
    markdown = _skill_path.read_text()
    section = _section(markdown, "## Workflow: Confirm and Generate")
    assert "DECORATIVE_LABEL" in section


def test_decorative_label_is_present_specifically_in_the_completed_generation_case():
    """The completed-generation case is the one most likely to be mistaken for an accurate
    diagram (data-model.md), so it is checked specifically, not just the section as a whole."""
    markdown = _skill_path.read_text()
    section = _section(markdown, "## Workflow: Confirm and Generate")
    completed_case_start = section.index("done: true` with a `response`")
    completed_case = section[completed_case_start:completed_case_start + 400]
    assert "DECORATIVE_LABEL" in completed_case


def test_decorative_label_is_present_in_the_get_world_fallback_case():
    markdown = _skill_path.read_text()
    section = _section(markdown, "## Workflow: Confirm and Generate")
    fallback_start = section.index("not_found_or_expired")
    fallback_case = section[fallback_start:fallback_start + 500]
    assert "DECORATIVE_LABEL" in fallback_case
