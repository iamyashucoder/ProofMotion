"""Verified, parameterised builders the model composes instead of writing layout code."""

from proofmotion.components import (
    advanced_jee,
    coordinate,
    core,
    fields,
    graphs,
    jee_visuals,
    mechanics,
    physics,
    story,
    trigonometry,
)

#: Referenced so a linter cannot prune these imports; registration is a side effect.
_REGISTERING_MODULES = (advanced_jee, coordinate, core, fields, graphs, jee_visuals, mechanics, physics, story, trigonometry)
from proofmotion.components.base import COMPONENTS, Built, Component, build, component

__all__ = ["COMPONENTS", "Built", "Component", "build", "component"]
