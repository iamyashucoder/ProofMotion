"""Safe cinematic action planning for reusable 2D/3D animation scenes."""

from __future__ import annotations

from typing import Any, Literal

from proofmotion.runtime.registry import ToolError, tool


@tool
def cinematic_chase_brief(
    duration_seconds: float = 36.0,
    frame_rate: Literal[24, 30] = 24,
    aspect_ratio: Literal["16:9"] = "16:9",
) -> dict[str, Any]:
    """Create a non-graphic, cinematic police-chase storyboard with camera and FX cues.

    This returns timing and visual requirements, not copyrighted audio. Use the
    returned sound cues as placeholders for licensed or original assets only.

    Args:
        duration_seconds: Total chase duration, from 20 to 60 seconds.
        frame_rate: 24 for cinematic motion or 30 for smoother motion.
        aspect_ratio: Output aspect ratio; currently 16:9.
    """
    if not 20 <= duration_seconds <= 60:
        raise ToolError("duration_seconds must be between 20 and 60")
    portions = (0.20, 0.25, 0.22, 0.18, 0.15)
    names = (
        ("pursuit_setup", "low road-level, side tracking, then wide establishing view"),
        ("nervous_swerve", "over-shoulder rider glance, safe pursuit spacing, lane movement"),
        ("traction_loss", "close rear-wheel shot, gravel particles, wobble, restrained camera shake"),
        ("non_graphic_crash", "rider separates safely, motorcycle slides to a tree, no injuries shown"),
        ("safe_resolution", "police brake, officers check consciousness, arrest, flashing-light end frame"),
    )
    shots = [
        {"scene_id": scene_id, "seconds": round(duration_seconds * fraction, 1), "camera": camera}
        for (scene_id, camera), fraction in zip(names, portions)
    ]
    return {
        "render": {"aspect_ratio": aspect_ratio, "resolution": "1920x1080", "frame_rate": frame_rate, "frames": round(duration_seconds * frame_rate)},
        "shots": shots,
        "continuity": ["keep the same motorcycle, police car, thief clothing, bag, road and tree models across every shot", "show police maintaining safe distance until the road hazard forces braking"],
        "effects": ["dust and loose gravel", "short skid marks", "brief non-graphic sparks at motorcycle-ground contact", "camera shake only during the slide/impact", "red-blue flashing light wash in final shot"],
        "audio_cues": ["motorcycle engine", "police siren", "tire/gravel skid", "subtle action music"],
        "safety": ["no blood, wounds, or body impact close-ups", "show the rider conscious before arrest", "avoid endorsing unsafe pursuit behaviour"],
    }


@tool
def vehicle_motion_profile(
    initial_speed_mps: float,
    braking_deceleration_mps2: float,
    reaction_seconds: float = 0.0,
    surface: Literal["dry_asphalt", "wet_asphalt", "loose_gravel"] = "dry_asphalt",
) -> dict[str, Any]:
    """Calculate believable braking and skid timing for a vehicle animation.

    Args:
        initial_speed_mps: Vehicle speed before braking.
        braking_deceleration_mps2: Positive braking magnitude in m/s².
        reaction_seconds: Delay before braking begins.
        surface: Road surface determining the visual traction warning.
    """
    if initial_speed_mps < 0 or braking_deceleration_mps2 <= 0 or reaction_seconds < 0:
        raise ToolError("speed and reaction_seconds must be non-negative; braking_deceleration_mps2 must be positive")
    braking_time = initial_speed_mps / braking_deceleration_mps2
    braking_distance = initial_speed_mps**2 / (2 * braking_deceleration_mps2)
    traction = {"dry_asphalt": "high", "wet_asphalt": "reduced", "loose_gravel": "low"}[surface]
    return {
        "reaction_distance_m": initial_speed_mps * reaction_seconds,
        "braking_distance_m": braking_distance,
        "total_stopping_distance_m": initial_speed_mps * reaction_seconds + braking_distance,
        "braking_time_seconds": braking_time,
        "surface_traction": traction,
        "animation_note": "Show a controlled wobble/skid only on reduced or low traction; do not make the vehicle stop instantly.",
    }


@tool
def non_graphic_action_audit(elements: list[str]) -> dict[str, Any]:
    """Audit an action storyboard for non-graphic, general-audience safety.

    Args:
        elements: Planned visual elements, camera beats, and outcomes.
    """
    text = " ".join(elements).lower()
    prohibited = ("blood", "gore", "bone", "wound close-up", "graphic injury", "corpse")
    issues = [term for term in prohibited if term in text]
    recommended = []
    if "conscious" not in text:
        recommended.append("show the rider conscious before any arrest")
    if "safe distance" not in text and "brake" not in text:
        recommended.append("show the pursuing vehicle braking and maintaining safe distance")
    return {"approved": not issues, "issues": issues, "recommendations": recommended}
