r"""Structured output has to carry LaTeX through JSON.

JSON permits only \" \\ \/ \b \f \n \r \t \uXXXX. Mathematics writes \phi,
\cos, \frac and \theta. Two different failures follow, and the second is the
dangerous one:

  \phi   is not a legal escape, so the payload fails to parse outright
  \frac  *is* legal — \f is a formfeed — so it parses and silently becomes
         a formfeed followed by "rac", and the run continues with corrupted
         notation that renders as nonsense

The rule below reads a control-letter escape as LaTeX whenever a letter follows
it, because a genuine tab or formfeed never appears mid-word in this payload.
"""

from __future__ import annotations

import unittest

from proofmotion.runtime.loop import extract_json


class LatexThroughJsonTests(unittest.TestCase):
    def test_escapes_json_rejects_outright(self):
        self.assertEqual(
            extract_json(r'{"eq": "N(\phi)=3mg(1+\cos\phi)"}')["eq"], r"N(\phi)=3mg(1+\cos\phi)"
        )
        self.assertEqual(extract_json(r'{"e": "\int_a^b f(x)\,dx"}')["e"], r"\int_a^b f(x)\,dx")

    def test_latex_beginning_with_a_control_letter_is_not_corrupted(self):
        """The silent-corruption case: these parse strictly and come back wrong."""
        for source, expected in [
            (r'{"a": "\frac{1}{2}mv^2"}', r"\frac{1}{2}mv^2"),
            (r'{"a": "\beta"}', r"\beta"),
            (r'{"a": "\theta"}', r"\theta"),
            (r'{"a": "\nabla f"}', r"\nabla f"),
            (r'{"a": "\rho"}', r"\rho"),
            (r'{"a": "\nu"}', r"\nu"),
        ]:
            with self.subTest(source=source):
                self.assertEqual(extract_json(source)["a"], expected)

    def test_genuine_control_characters_survive(self):
        """A newline or tab followed by anything but a letter stays a control character."""
        for source, expected in [
            ('{"a": "one\\n two"}', "one\n two"),
            ('{"a": "end\\n"}', "end\n"),
            ('{"a": "x\\n2"}', "x\n2"),
            ('{"a": "a\\t b"}', "a\t b"),
        ]:
            with self.subTest(source=source):
                self.assertEqual(extract_json(source)["a"], expected)

    def test_already_escaped_latex_is_left_alone(self):
        self.assertEqual(extract_json(r'{"e": "\\sin x"}')["e"], r"\sin x")

    def test_quotes_and_unicode_escapes_still_work(self):
        self.assertEqual(extract_json('{"a": "say \\"hi\\""}')["a"], 'say "hi"')
        self.assertEqual(extract_json(r'{"u": "é"}')["u"], "é")

    def test_fenced_output_carrying_notation(self):
        payload = "Here:\n```json\n" + r'{"eq": "\alpha + \beta"}' + "\n```\ndone"
        self.assertEqual(extract_json(payload)["eq"], r"\alpha + \beta")

    def test_a_realistic_storyboard_round_trips(self):
        payload = (
            r'{"teaching_strategy": "energy first", "scenes": [{"equations": '
            r'["N(\phi)=3mg(1+\cos\phi)", "\frac{1}{2}mv^2 + mgy", "\theta \to 0"]}]}'
        )
        equations = extract_json(payload)["scenes"][0]["equations"]
        self.assertEqual(equations[0], r"N(\phi)=3mg(1+\cos\phi)")
        self.assertEqual(equations[1], r"\frac{1}{2}mv^2 + mgy")
        self.assertEqual(equations[2], r"\theta \to 0")

    def test_unparseable_output_still_raises(self):
        with self.assertRaises(ValueError):
            extract_json("no json here at all")


if __name__ == "__main__":
    unittest.main()
