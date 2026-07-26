"""Deterministic assembly: the model picks components, Python writes the scene."""

from proofmotion.compose.assembler import (
    SceneAssignment,
    ScenePlan,
    assemble,
    check,
    coverage,
    estimated_seconds,
    pictorial_coverage,
)
from proofmotion.compose.derive import plan_from_storyboard
from proofmotion.compose.selector import select_components

__all__ = [
    "SceneAssignment",
    "ScenePlan",
    "assemble",
    "check",
    "coverage",
    "estimated_seconds",
    "pictorial_coverage",
    "plan_from_storyboard",
    "select_components",
]
