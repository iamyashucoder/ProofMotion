# ProofMotion development environment.
#   source scripts/env.sh
#
# This machine's root partition (/) is 100% full, so uv's cache, uv's managed
# Python, and TinyTeX all live on SSD1 rather than under $HOME. Adjust
# PROOFMOTION_TOOLS if you relocate them.

PROOFMOTION_TOOLS="${PROOFMOTION_TOOLS:-/media/mbzuaiser/SSD1/Komal}"

# uv: keep cache and managed interpreters off the full root partition.
export UV_CACHE_DIR="$PROOFMOTION_TOOLS/.uv/cache"
export UV_PYTHON_INSTALL_DIR="$PROOFMOTION_TOOLS/.uv/python"

# TinyTeX: userspace TeX Live (no root available on this box).
# Required by manim's MathTex/Tex on the export path. TypstMath does not need it.
export PATH="$PROOFMOTION_TOOLS/.texlive/bin/x86_64-linux:$PATH"

echo "ProofMotion env ready"
echo "  uv cache : $UV_CACHE_DIR"
echo "  latex    : $(command -v latex || echo 'NOT FOUND')"
echo "  typst    : python package (no binary needed)"
