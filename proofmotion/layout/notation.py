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
    "—": "--", "–": "-", "…": r"\ldots",
    "“": "``", "”": "''", "‘": "`", "’": "'",
}

#: Spaces that are not the space character. A model writing "20 m/s" reaches
#: for a narrow no-break space between the number and its unit, and the
#: character is invisible in every log and error message it later appears in:
#: the render died on U+202F and the message named a file in vendored Manim.
SPACES = {
    " ": " ", " ": " ", " ": " ", " ": " ",
    " ": " ", " ": " ", " ": " ", " ": " ",
    "\u200b": "", "﻿": "",
}
SYMBOLS.update(SPACES)

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


#: An actual LaTeX command. Only LaTeX can set these.
_COMMAND = re.compile(r"\\[A-Za-z]+")
#: Notation that only means something in math mode.
_MATHS = re.compile(r"[\^_]|[=<>≤≥≈]")
#: Three or more ordinary words in a row reads as a sentence.
_PROSE = re.compile(r"(?:\b[A-Za-z]{2,}\b[ ,]+){3,}")


def looks_like_maths(text: str) -> bool:
    """Whether this caption should be set as mathematics rather than as text.

    A LaTeX command decides it, before anything else is considered. Text cannot
    set ``\\sin`` or ``\\theta`` at all — it draws the backslash — and that is
    the gibberish that reached finished videos: ``x\\text{-axis: down the
    incline}`` has three ordinary words in it, so a prose-first rule sent
    correct LaTeX to a mobject with no LaTeX in it.

    The author already said which they meant. ``\\text{}`` around words *is* the
    instruction to set them upright inside mathematics, and MathTex honours it.

    With no commands present the question is real, and prose wins: MathTex sets
    an English sentence in italic maths with the spaces stripped out.
    """
    stripped = (text or "").strip()
    if not stripped:
        return False
    if _COMMAND.search(stripped):
        return True
    if _PROSE.search(stripped):
        return False
    return bool(_MATHS.search(stripped)) or " " not in stripped


#: The reverse of SYMBOLS, for showing LaTeX to a person instead of setting it.
#: Built from the same table so the two cannot describe different notation.
_FROM_LATEX = {
    latex: char
    for char, latex in SYMBOLS.items()
    if latex.startswith("\\") and char not in SPACES
}
#: Commands that decorate their argument. The decoration is not worth a
#: mangled word in a chat line, so the argument is kept and the wrapper goes.
_WRAPPER = re.compile(
    r"\\(?:text|mathrm|mathbf|mathit|mathsf|operatorname|vec|hat|bar|dot|ddot|tilde)\s*\{([^{}]*)\}"
)
_FRACTION = re.compile(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_SQRT = re.compile(r"\\sqrt\s*\{([^{}]*)\}")
_SCRIPT = re.compile(r"([_^])\{([^{}]*)\}|([_^])([0-9A-Za-z+\-])")
_SPACING = re.compile(r"\\(?:,|;|:|!|quad|qquad|left|right|displaystyle|;)")
_COMMAND_LEFT = re.compile(r"\\([A-Za-z]+)")


def readable(latex: str) -> str:
    """Turn LaTeX back into something a person reads in a chat window.

    The chat had been showing raw source — ``\\sum F_x = mg\\sin\\theta`` — which
    is exactly the gibberish complained about on screen, in the one place where
    there is no renderer to set it. This is the inverse of `to_latex`, built
    from the same table so the two cannot drift into describing different
    notation.
    """
    if not latex:
        return ""
    text = _SPACING.sub(" ", latex)
    text = _WRAPPER.sub(r"\1", text)
    text = _FRACTION.sub(r"(\1)/(\2)", text)
    text = _SQRT.sub(r"√(\1)", text)
    for command, char in _FROM_LATEX.items():
        text = text.replace(command, char)
    # Degrees before the script pass, or "^\circ" becomes "^°" with the caret
    # stranded: the degree sign already carries the raised position.
    text = re.sub(r"\^\s*\{?\s*\\circ\s*\}?", "°", text)
    text = text.replace(r"\circ", "°")
    # Scripts after the symbols, so \theta^{2} has already become θ. Braced and
    # bare forms both, because "x^2" is as common as "x^{2}".
    def script(match: re.Match[str]) -> str:
        mark = match.group(1) or match.group(3)
        body = match.group(2) if match.group(2) is not None else match.group(4)
        table = SUPERSCRIPTS_OUT if mark == "^" else SUBSCRIPTS_OUT
        return "".join(table.get(c, c) for c in body)

    text = _SCRIPT.sub(script, text)
    # Anything left keeps its name and loses the backslash, with a space so a
    # function does not weld itself to its argument: "mg\sin\theta" reads as
    # "mg sin θ" rather than "mgsinθ".
    text = _COMMAND_LEFT.sub(r"\1 ", text)
    return re.sub(r"\s{2,}", " ", text.replace("{", "").replace("}", "")).strip()


#: Digits back to the superscript and subscript characters, for `readable`.
SUPERSCRIPTS_OUT = {v: k for k, v in SUPERSCRIPTS.items()}
SUBSCRIPTS_OUT = {v: k for k, v in SUBSCRIPTS.items()}


def unsupported(text: str) -> list[str]:
    """Characters LaTeX still cannot set after translation.

    Reported rather than silently dropped: a character nobody has a spelling
    for is a gap in the table, and it should be visible as one.
    """
    return sorted({c for c in to_latex(text) if ord(c) > 127})
