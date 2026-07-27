"""The studio: a durable document, rendered as clips and joined."""

from proofmotion.studio.document import Project, Slide
from proofmotion.studio.render import Unit, build, digest_of, group, join, render_project, units_of

__all__ = [
    "Project",
    "Slide",
    "Unit",
    "build",
    "digest_of",
    "group",
    "join",
    "render_project",
    "units_of",
]
