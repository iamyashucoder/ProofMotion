"""Unicode maths, turned into LaTeX that actually compiles.

A model asked for a caption writes what it would write anywhere: ``sum ≈ 9.86``,
``∫₀³ x² dx``. Those characters are perfectly good mathematics and `MathTex`
cannot compile any of them — the render dies with "LaTeX Error: Unicode" long
after the point where anyone could see which character caused it.

This is not a nicety. Three clips in a row failed on ``≈`` alone, and the
message that came back named a file in vendored Manim rather than the caption
the person had just asked for.

Translating is the right response rather than refusing. The notation is correct;
only the encoding is wrong, and there is exactly one LaTeX spelling for each of
these.
"""

from __future__ import annotations

import re

#: Single characters with an unambiguous LaTeX spelling.
SYMBOLS = {
    # Greek, lower and upper.
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta",
    "ε": r"\epsilon", "ζ": r"\zeta", "η": r"\eta", "θ": r"\theta",
    "ι": r"\iota", "κ": r"\kappa", "λ": r"\lambda", "μ": r"\mu",
    "ν": r"\nu", "ξ": r"\xi", "π": r"\pi", "ρ": r"\rho",
    "σ": r"\sigma", "τ": r"\tau", "υ": r"\upsilon", "φ": r"\phi",
    "χ": r"\chi", "ψ": r"\psi", "ω": r"\omega",
    "Γ": r"\Gamma", "Δ": r"\Delta", "Θ": r"\Theta", "Λ": r"\Lambda",
    "Ξ": r"\Xi", "Π": r"\Pi", "Σ": r"\Sigma", "Φ": r"\Phi",
    "Ψ": r"\Psi", "Ω": r"\Omega",
    # Relations and operators.
    "≈": r"\approx", "≠": r"\neq", "≤": r"\leq", "≥": r"\geq",
    "≡": r"\equiv", "∼": r"\sim", "∝": r"\propto", "±": r"\pm",
    "∓": r"\mp", "×": r"\times", "÷": r"\div", "·": r"\cdot",
    "→": r"\to", "←": r"\leftarrow", "↔": r"\leftrightarrow",
    "⇒": r"\Rightarrow", "⇐": r"\Leftarrow", "⇔": r"\Leftrightarrow",
    "∞": r"\infty", "∂": r"\partial", "∇": r"\nabla", "√": r"\sqrt{}",
    "∫": r"\int", "∮": r"\oint", "∑": r"\sum", "∏": r"\prod",
    "∈": r"\in", "∉": r"\notin", "⊂": r"\subset", "⊆": r"\subseteq",
    "∪": r"\cup", "∩": r"\cap", "∅": r"\emptyset",
    "∀": r"\forall", "∃": r"\exists", "¬": r"\neg",
    "∧": r"\wedge", "∨": r"\vee", "⊥": r"\perp", "∥": r"\parallel",
    "∠": r"\angle", "°": r"^{\circ}", "′": r"'", "″": r"''",
    "ℝ": r"\mathbb{R}", "ℕ": r"\mathbb{N}", "ℤ": r"\mathbb{Z}",
    "ℚ": r"\mathbb{Q}", "ℂ": r"\mathbb{C}",
    # Punctuation a model reaches for that LaTeX does not know.
    "—": "--", "–": "-", "…": r"\ldots", " ": " ",
    "“": "``", "”": "''", "‘": "`", "’": "'",
}

#: Superscript and subscript digits, which arrive as ``x²`` and ``∫₀³``.
SUPERSCRIPTS = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
                "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
                "⁺": "+", "⁻": "-", "⁽": "(", "⁾": ")", "ⁿ": "n"}
SUBSCRIPTS = {"₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
              "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
              "₊": "+", "₋": "-", "₍": "(", "₎": ")", "ₙ": "n"}

_SUPER = re.compile(f"[{''.join(SUPERSCRIPTS)}]+")
_SUB = re.compile(f"[{''.join(SUBSCRIPTS)}]+")


_SYMBOL = re.compile("[" + re.escape("".join(SYMBOLS)) + "]")


def _spell(match: re.Match[str], source: str) -> str:
    """One symbol, spaced off the letter after it when TeX would run them together.

    ``Δv`` must become ``\\Delta v``: TeX reads ``\\Deltav`` as a single
    undefined command, so translating without the space fails exactly like the
    Unicode it replaced. The space is added here, where the following character
    is known — a regex over the finished string cannot do it, because a greedy
    control word with a lookahead backtracks into itself and yields
    ``\\alph a``.
    """
    latex = SYMBOLS[match.group()]
    following = source[match.end() : match.end() + 1]
    if latex.startswith("\\") and latex[-1].isalpha() and following.isalpha():
        return latex + " "
    return latex


def to_latex(text: str) -> str:
    """Rewrite Unicode mathematics as LaTeX source.

    Runs of superscripts collapse into one group, so ``x¹²`` becomes ``x^{12}``
    rather than ``x^{1}^{2}``, which is a LaTeX error of its own.
    """
    if not text:
        return text
    result = _SUPER.sub(lambda m: "^{" + "".join(SUPERSCRIPTS[c] for c in m.group()) + "}", text)
    result = _SUB.sub(lambda m: "_{" + "".join(SUBSCRIPTS[c] for c in m.group()) + "}", result)
    return _SYMBOL.sub(lambda m: _spell(m, result), result)


def unsupported(text: str) -> list[str]:
    """Characters LaTeX still cannot set after translation.

    Reported rather than silently dropped: a character nobody has a spelling
    for is a gap in the table, and it should be visible as one.
    """
    return sorted({c for c in to_latex(text) if ord(c) > 127})
