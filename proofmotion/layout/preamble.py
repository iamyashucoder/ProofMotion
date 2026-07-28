"""Packages a mathematics explanation actually reaches for.

Manim's default preamble is babel, amsmath and amssymb. That covers most
notation and misses some a teacher uses constantly — a slide crossing the mass
out of both sides of an equation wrote ``\\cancel{m}``, which is exactly the
right notation and is not in amsmath. The render died inside vendored Manim
with a compile error nobody could read, for a caption that was correct.

These are added once, on import. Every package here is small, standard, and
already installed with TinyTeX; nothing is added speculatively, only after
something that should have worked did not.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

#: Package, and the notation it exists to allow.
EXTRA_PACKAGES = {
    "cancel": r"\cancel{m}, for striking a term out of both sides",
    "mathtools": r"\coloneqq and friends",
    "siunitx": r"\SI{9.8}{m/s^2}, for a quantity with its unit",
}

_APPLIED = False


def ensure_packages() -> bool:
    """Add the packages to Manim's template. Safe to call repeatedly.

    Returns whether anything was added, so a caller can tell the difference
    between "already there" and "not available".
    """
    global _APPLIED
    if _APPLIED:
        return False
    _APPLIED = True

    try:
        from manim import config

        template = config.tex_template
    except Exception as error:  # noqa: BLE001 - a missing template is not fatal
        log.warning("could not reach the LaTeX template: %s", error)
        return False

    added = False
    for package in EXTRA_PACKAGES:
        if package in template.preamble:
            continue
        if not installed(package):
            # A package in the preamble that TeX cannot find fails *every*
            # compile, not just the ones using it. Adding these three blind
            # broke "a = 4.9" — which had nothing to do with any of them.
            log.warning("LaTeX package %r is not installed; leaving it out", package)
            continue
        template.add_to_preamble(rf"\usepackage{{{package}}}")
        added = True
    return added


def installed(package: str) -> bool:
    """Whether TeX can actually find this package."""
    import shutil
    import subprocess

    if not shutil.which("kpsewhich"):
        return False
    try:
        found = subprocess.run(
            ["kpsewhich", f"{package}.sty"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(found.stdout.strip())
