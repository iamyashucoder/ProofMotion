"""Verified, parameterised builders the model composes instead of writing layout code."""

from proofmotion.components import core, graphs, physics

#: Referenced so a linter cannot prune these imports; registration is a side effect.
_REGISTERING_MODULES = (core, graphs, physics)
from proofmotion.components.base import COMPONENTS, Built, Component, build, component

__all__ = ["COMPONENTS", "Built", "Component", "build", "component"]
