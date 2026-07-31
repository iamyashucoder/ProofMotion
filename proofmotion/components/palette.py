"""The deck's look, as one mutable palette the components read at build time.

Colors were scattered per module and inconsistent — two different greens both
called ACCENT, the same ink written out twice — and none of it was choosable:
the deck looked like the constants, forever. A preset is a coherent set of
roles; `activate` copies it onto the one PALETTE instance and sets Manim's
defaults, so every component and every caption restyles without a call site
changing.

The build functions read PALETTE attributes at build time, after `activate`
has run in the render process — which is why the singleton is mutated in
place and never rebound: a module-level `from palette import PALETTE` must
keep seeing the change.

Known limitation: genuinely physical colors (copper wire, a road's grey) are
content, not chrome, and stay hard-coded in their components — on the light
`paper` preset those few keep their dark-background contrast choices.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from proofmotion.runtime.registry import ToolError


@dataclass
class Palette:
    name: str
    background: str  #: scene background
    ink: str         #: default Text/MathTex color
    muted: str       #: secondary strokes, plain arrows
    axis: str        #: axis lines and ticks
    accent: str      #: the primary accent
    secondary: str   #: the second accent — fields, mechanics
    highlight: str   #: attention, warmth
    good: str        #: converges, correct
    bad: str         #: diverges, error
    font: str = ""   #: Text font family; empty keeps Manim's default


PRESETS: dict[str, Palette] = {
    # Today's exact values, so the default deck is byte-identical to before.
    "dark": Palette(
        name="dark", background="#000000", ink="#e6edf3", muted="#64748b",
        axis="#9aa7bd", accent="#4aa3df", secondary="#4ade80",
        highlight="#fbbf24", good="#4ade80", bad="#f87171",
    ),
    "paper": Palette(
        name="paper", background="#faf7f0", ink="#1f2430", muted="#64748b",
        axis="#475569", accent="#2563eb", secondary="#059669",
        highlight="#d97706", good="#059669", bad="#dc2626",
    ),
    "chalkboard": Palette(
        name="chalkboard", background="#233d33", ink="#f2efe4", muted="#9fb3a8",
        axis="#cfd8c9", accent="#9bd1e5", secondary="#b9f6ca",
        highlight="#ffe066", good="#b9f6ca", bad="#ff8a80",
    ),
    "minimal": Palette(
        name="minimal", background="#0e0e0e", ink="#f5f5f5", muted="#52525b",
        axis="#6b7280", accent="#e2e8f0", secondary="#94a3b8",
        highlight="#38bdf8", good="#94f7c8", bad="#f87171",
    ),
}

#: The palette every component reads. Mutated in place by `activate`.
PALETTE = dataclasses.replace(PRESETS["dark"])


def activate(name: str) -> Palette:
    """Make a preset current, in this process and in Manim's defaults.

    Called from the emitted scene source before the scene class is defined,
    so the render subprocess draws with the deck's palette. `set_default` is
    the load-bearing trick: it restyles the default-white text of every
    component and the assembler's titles and captions without touching any
    call site.
    """
    preset = PRESETS.get(name)
    if preset is None:
        raise ToolError(f"unknown style {name!r}; available: {sorted(PRESETS)}")
    for slot in dataclasses.fields(Palette):
        setattr(PALETTE, slot.name, getattr(preset, slot.name))

    from manim import MathTex, Tex, Text, config

    config.background_color = PALETTE.background
    text_defaults = {"color": PALETTE.ink}
    if PALETTE.font:
        text_defaults["font"] = PALETTE.font
    Text.set_default(**text_defaults)
    MathTex.set_default(color=PALETTE.ink)
    Tex.set_default(color=PALETTE.ink)
    return PALETTE
