import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

MODEL_NAME = os.getenv(
    "OPENROUTER_MODEL",
    "google/gemma-3-27b-it",
)


def ask_gemma(system_prompt: str, user_prompt: str) -> str | None:
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        print("\nERROR: OPENROUTER_API_KEY was not found in .env")
        return None

    print(f"\nSending request to {MODEL_NAME} through OpenRouter...")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=0.2,
            max_tokens=4000,
        )

        content = response.choices[0].message.content

        if not content:
            print("\nERROR: Gemma returned an empty response.")
            return None

        print("\nGemma responded successfully.")
        return content

    except Exception as error:
        print("\nERROR: OpenRouter request failed:")
        print(type(error).__name__)
        print(error)
        return None
import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

MODEL_NAME = os.getenv(
    "OPENROUTER_MODEL",
    "google/gemma-3-27b-it",
)


def ask_gemma(system_prompt: str, user_prompt: str) -> str | None:
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        print("\nERROR: OPENROUTER_API_KEY was not found in .env")
        return None

    print(f"\nSending request to {MODEL_NAME} through OpenRouter...")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=0.2,
            max_tokens=4000,
        )

        content = response.choices[0].message.content

        if not content:
            print("\nERROR: Gemma returned an empty response.")
            return None

        print("\nGemma responded successfully.")
        return content

    except Exception as error:
        print("\nERROR: OpenRouter request failed:")
        print(type(error).__name__)
        print(error)
        return None
def repair_manim_code(
    original_prompt: str,
    broken_code: str,
    render_error: str,
) -> str | None:
    
    system_prompt = """
You are an expert Manim Community Edition debugging agent.

Repair the provided Manim program.

Strict rules:
1. Return the complete corrected Python program.
2. Return Python code only.
3. Do not include Markdown code fences.
4. Keep exactly one Scene subclass named GeneratedScene.
5. Preserve the user's original animation request.
6. Use only valid Manim Community Edition APIs.
7. Do not use os, subprocess, requests, socket, open, eval, or exec.
8. Fix the error shown in the render log.
9. Axes does not have add_axis_labels().
10. Axes does not have add_coordinate_labels().
11. For axis labels, use axes.get_axis_labels().
12. For coordinates, use axes.c2p(x, y).
13. Do not use axes.coords_to_point().
20. A ValueTracker must be animated using:
    self.play(
        tracker.animate.set_value(new_value),
        run_time=5,
        rate_func=linear,
    )

21. Never use:
    tracker.animate(rate=..., run_time=..., end_value=...)

22. A Manim updater must accept either:
    def updater(mobject):
or:
    def updater(mobject, dt):

23. An updater does not receive the ValueTracker value automatically.
    Read it using tracker.get_value().

24. Prefer always_redraw with ValueTracker for moving objects along graphs.

25. Do not index a Polygon as polygon[0], polygon[1], or polygon[2] to access its sides.

26. To position labels on polygon edges, use polygon.get_vertices() and compute edge midpoints.

27. A Polygon is a single Manim mobject, not a list of separate Line objects.

28. Use Create(triangle), not Create(axes), when introducing a triangle scene.

25. For array or algorithm animations, do not use Axes unless a graph is required.

26. Represent arrays using a VGroup of Rectangle or Square cells containing Text objects.

27. Keep each array value centered inside its own cell.

28. Represent Low, Mid, and High using arrows or labels positioned under the corresponding cells.

29. When a pointer changes index, animate it using Transform or animate.move_to().

30. Do not reveal or highlight the target cell before the algorithm reaches it.

31. Store temporary Text, Rectangle, and comparison objects in variables before fading them out.

32. Never create a new object inside FadeOut() as a replacement for an already visible object.

33. For binary search, visibly fade or dim the discarded half of the array.

34. Verify that the displayed low, mid, and high indices match the algorithm state.

For array visualizations:
- Use VGroup containing Square or Rectangle cells.
- Do not use coordinate axes unless required.
- Keep all values inside the frame.
- Pointer labels must physically move to the correct array cells.
- Do not use Text.set_value().
- Update Text using Transform(old_text, new_text).
- Do not create a new temporary Text object directly inside FadeOut().

For layout repair:

- Center the full animation composition horizontally.
- Scale wide VGroups to fit inside the frame.
- Ensure all array cells and values are visible.
- Keep at least 0.3 units of margin from frame edges.
- Move overlapping labels, comparison text, and result text to separate rows.
- Place Low, Mid, and High arrows directly below their correct cells.
- Animate pointer changes using Transform.
- Do not reveal the target cell before the correct search step.
- Keep the final result fully visible near the bottom of the frame.
- Reduce unnecessary self.wait() calls if the animation is too long.
"""
    


    user_prompt = f"""
ORIGINAL ANIMATION REQUEST:
{original_prompt}

BROKEN MANIM CODE:
{broken_code}

MANIM RENDER ERROR:
{render_error}
"""

    return ask_gemma(system_prompt, user_prompt)