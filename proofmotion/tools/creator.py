"""Planning tools for creators making clear, high-motion study animations.

The tools specify an independent clarity-first educational workflow. They do
not reproduce any creator's branding, voice, assets, or visual identity.
"""

from __future__ import annotations

from typing import Any, Literal

from proofmotion.runtime.registry import ToolError, tool


@tool
def study_animation_brief(
    topic: str,
    audience: str = "senior-school student",
    format: Literal["short_lesson", "worked_problem", "concept_explainer", "exam_revision"] = "concept_explainer",
) -> dict[str, Any]:
    """Create visual and motion requirements for a study-animation creator.

    The output is an independent clarity-first briefing: intuition before a
    formal definition, a picture that explains the claim, and only purposeful
    movement. Use it before storyboarding creator or study-content prompts.

    Args:
        topic: The exact concept or question being explained.
        audience: Learner level, used to choose vocabulary and pacing.
        format: short_lesson, worked_problem, concept_explainer, or exam_revision.
    """
    lowered = topic.lower()
    motion: list[dict[str, str]] = [
        {"primitive": "staged_reveal", "purpose": "introduce one visual relationship at a time"},
        {"primitive": "continuity_transform", "purpose": "keep an object or equation visually identifiable while it changes"},
        {"primitive": "camera_focus", "purpose": "move attention to the local detail currently being explained"},
    ]
    visual_patterns: list[str] = ["concrete setup", "labelled diagram", "one changing quantity", "formal statement", "recap"]
    if any(word in lowered for word in ("derivative", "integral", "limit", "graph", "function", "rate")):
        motion.extend([
            {"primitive": "continuous_parameter", "purpose": "show a point, tangent, or interval changing continuously"},
            {"primitive": "traced_motion", "purpose": "leave a visible record of the changing quantity"},
        ])
        visual_patterns.extend(["axes and graph", "local-to-global comparison"])
    if any(word in lowered for word in ("matrix", "vector", "linear transformation", "eigen", "determinant")):
        motion.extend([
            {"primitive": "spatial_transform", "purpose": "show vectors and a grid changing together under a map"},
            {"primitive": "before_after_overlay", "purpose": "preserve a reference grid while comparing the transformation"},
        ])
        visual_patterns.extend(["basis vectors", "grid deformation", "invariant or area comparison"])
    if any(word in lowered for word in ("motion", "force", "car", "bus", "projectile", "orbit", "collision")):
        motion.extend([
            {"primitive": "path_follow", "purpose": "make position and velocity visible as physical motion"},
            {"primitive": "linked_graph", "purpose": "connect the object’s motion to a live graph or vector"},
        ])
        visual_patterns.extend(["physical objects", "arrows for vectors", "data/graph view"])
    return {
        "topic": topic,
        "audience": audience,
        "format": format,
        "required_story_order": [
            "open with a motivating question or concrete situation",
            "build the visual model before naming the formal rule",
            "animate the key relationship continuously or through matched transforms",
            "derive only the mathematics the visual has motivated",
            "test the idea on one example and recap the transferable insight",
        ],
        "required_visual_rules": [
            "every moving object must communicate the same point as the narration",
            "keep a reference object on screen during a transformation when comparison matters",
            "label quantities at the moment they become relevant",
            "prefer a readable new beat over shrinking text",
            "do not use decorative motion or equations moving without explanatory purpose",
        ],
        "motion_primitives": motion,
        "visual_patterns": list(dict.fromkeys(visual_patterns)),
        "creator_checklist": [
            "Can a learner infer the key claim with sound off?",
            "Does each animation have a named teaching purpose?",
            "Does the first minute create intuition before formal notation?",
            "Does the final frame state what the learner should remember?",
        ],
    }


@tool
def study_animation_timing(
    teaching_beats: int,
    format: Literal["short_lesson", "worked_problem", "concept_explainer", "exam_revision"] = "concept_explainer",
) -> dict[str, Any]:
    """Allocate readable timing for an educational animation without rushing it.

    Args:
        teaching_beats: Number of distinct ideas or visible changes.
        format: The intended study-content format.
    """
    if not 3 <= teaching_beats <= 20:
        raise ToolError("teaching_beats must be between 3 and 20")
    seconds_per_beat = {"short_lesson": 5.5, "worked_problem": 9.0, "concept_explainer": 7.0, "exam_revision": 6.0}[format]
    total = teaching_beats * seconds_per_beat
    return {
        "format": format, "teaching_beats": teaching_beats, "recommended_seconds": round(total, 1),
        "suggested_structure": {
            "hook_and_setup_seconds": round(max(4.0, total * 0.12), 1),
            "visual_intuition_seconds": round(total * 0.32, 1),
            "derivation_or_worked_steps_seconds": round(total * 0.4, 1),
            "recap_seconds": round(max(4.0, total * 0.16), 1),
        },
        "note": "A new teaching beat earns time when the viewer must observe a change; do not add pauses merely to reach a target duration.",
    }


@tool
def motion_design_audit(animations: list[dict[str, Any]]) -> dict[str, Any]:
    """Reject decorative animations that do not have a teaching purpose.

    Args:
        animations: Each item needs a primitive and purpose; optionally include narration_point and visual_change.
    """
    issues: list[dict[str, str]] = []
    for index, animation in enumerate(animations):
        primitive = str(animation.get("primitive", "")).strip()
        purpose = str(animation.get("purpose", "")).strip()
        if not primitive:
            issues.append({"index": str(index), "issue": "missing motion primitive"})
        if not purpose:
            issues.append({"index": str(index), "issue": "missing teaching purpose; remove or justify this motion"})
        if primitive in {"spin", "bounce", "flash"} and len(purpose) < 20:
            issues.append({"index": str(index), "issue": "ornamental motion has no sufficiently specific learning purpose"})
    return {
        "approved": not issues, "checked": len(animations), "issues": issues,
        "verdict": "motion supports the lesson" if not issues else "revise or remove the listed decorative motion",
    }
