"""Agents: a goal, a toolset, and a schema. No domain knowledge.

The agents these replace branched on `if "gradient descent" in prompt`, which
meant the system understood exactly three topics and stubbed everything else.
Nothing here mentions a topic. Generality comes from the tools.
"""

from proofmotion.agents.coder import write_scene
from proofmotion.agents.director import direct_storyboard
from proofmotion.agents.intent import understand_request
from proofmotion.agents.planner import plan_mathematics
from proofmotion.agents.verifier import verify_plan

__all__ = [
    "direct_storyboard",
    "plan_mathematics",
    "understand_request",
    "verify_plan",
    "write_scene",
]
