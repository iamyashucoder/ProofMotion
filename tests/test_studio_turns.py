"""The fallback ladder, rung by rung.

Every branch in turns.py exists because of a session that went wrong, so each
rung is held still here with recording fakes: which agent answers, in what
order, and what reaches the person when a turn wobbles.

No API key required.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from proofmotion.studio import Project, Slide
from proofmotion.studio.operations import Edit, Operation
from proofmotion.studio.turns import run_turn

ADD = Operation(kind="add", title="a slide")


def empty_project() -> Project:
    return Project.create("test", "")


def deck() -> Project:
    p = Project.create("test", "a question")
    p.slides = [Slide(id="s1", title="One")]
    return p


class Recorder:
    """A stand-in agent that logs its call and returns what it was told to."""

    def __init__(self, name: str, log: list, result):
        self.name, self.log, self.result = name, log, result

    def __call__(self, *args, **kwargs):
        self.log.append((self.name, args[1:] if args else (), kwargs))
        return self.result


def ladder(log, **results):
    """Patch every agent the ladder can reach with recording fakes."""
    return (
        patch("proofmotion.studio.compose_full.answer_fully",
              Recorder("answer_fully", log, results.get("answer_fully", ([], "")))),
        patch("proofmotion.agents.studio.propose",
              Recorder("propose", log, results.get("propose", Edit()))),
        patch("proofmotion.studio.compose_full.derive_anyway",
              Recorder("derive_anyway", log, results.get("derive_anyway", ([], "")))),
        patch("proofmotion.studio.compose_full.draw_by_hand",
              Recorder("draw_by_hand", log, results.get("draw_by_hand", ([], "")))),
    )


def climbed(project, message, log, *, remake_slide="", **results):
    patches = ladder(log, **results)
    for p in patches:
        p.start()
    try:
        return run_turn(None, project, message, remake_slide=remake_slide)
    finally:
        for p in patches:
            p.stop()


class TestOpeningQuestion(unittest.TestCase):
    def test_the_full_pipeline_answers_first(self):
        log = []
        result = climbed(empty_project(), "why", log, answer_fully=([ADD], "done"))
        self.assertEqual([name for name, *_ in log], ["answer_fully"])
        self.assertEqual(result.edit.operations, [ADD])
        self.assertEqual(result.edit.reply, "done")

    def test_an_empty_pipeline_falls_to_the_edit_agent(self):
        log = []
        result = climbed(empty_project(), "animate a square", log,
                         propose=Edit(operations=[ADD], reply="drawn"))
        self.assertEqual([name for name, *_ in log], ["answer_fully", "propose"])
        self.assertEqual(result.edit.operations, [ADD])

    def test_the_hand_drawn_flag_is_honoured(self):
        log = []
        climbed(empty_project(), "morph it", log,
                propose=Edit(needs_hand_drawn="a square becoming a circle"),
                draw_by_hand=([ADD], "drew it"))
        self.assertEqual([name for name, *_ in log],
                         ["answer_fully", "propose", "draw_by_hand"])
        # The coder is briefed with the scene description, not the raw message.
        self.assertEqual(log[-1][1], ("a square becoming a circle",))

    def test_an_empty_answer_gets_a_forced_derivation_before_hand_drawing(self):
        """An empty answer is a turn that went wrong, not an empty catalogue."""
        log = []
        climbed(empty_project(), "projectile motion", log,
                derive_anyway=([ADD], "worked through"))
        self.assertEqual([name for name, *_ in log],
                         ["answer_fully", "propose", "derive_anyway"])

    def test_hand_drawing_is_the_last_resort(self):
        log = []
        result = climbed(empty_project(), "something odd", log,
                         draw_by_hand=([ADD], "by hand then"))
        self.assertEqual([name for name, *_ in log],
                         ["answer_fully", "propose", "derive_anyway", "draw_by_hand"])
        self.assertEqual(result.edit.reply, "by hand then")


class TestFollowUp(unittest.TestCase):
    def test_an_edit_is_an_edit(self):
        log = []
        result = climbed(deck(), "make it blue", log,
                         propose=Edit(operations=[ADD], reply="made blue"))
        self.assertEqual([name for name, *_ in log], ["propose"])
        self.assertEqual(result.edit.reply, "made blue")

    def test_the_hand_drawn_flag_keeps_the_slide_it_is_replacing(self):
        log = []
        climbed(deck(), "redraw it", log, remake_slide="s1",
                propose=Edit(operations=[ADD], needs_hand_drawn="the picture"),
                draw_by_hand=([ADD], "redrawn"))
        self.assertEqual([name for name, *_ in log], ["propose", "draw_by_hand"])
        _, args, kwargs = log[-1]
        self.assertEqual(args, ("the picture",))
        self.assertEqual(kwargs, {"existing": [ADD], "replacing": "s1"})

    def test_a_question_needing_derivation_escalates_to_the_pipeline(self):
        log = []
        climbed(deck(), "now add air resistance", log,
                propose=Edit(needs_full_derivation=True),
                answer_fully=([ADD], "derived"))
        self.assertEqual([name for name, *_ in log], ["propose", "answer_fully"])

    def test_a_remake_never_escalates(self):
        """Escalating from a remake box loses the one thing that box means."""
        log = []
        result = climbed(deck(), "how do we find pi?", log, remake_slide="s1",
                         propose=Edit(needs_full_derivation=True))
        self.assertEqual([name for name, *_ in log], ["propose"])
        self.assertEqual(result.edit.operations, [])
        self.assertIn("main box", result.refusal)


if __name__ == "__main__":
    unittest.main()
