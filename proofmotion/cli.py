import argparse
import logging

from proofmotion.pipeline import create_math_animation


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan, verify, preview, and render mathematical Manim animations.")
    parser.add_argument("prompt", nargs="?", help="Mathematical animation request")
    parser.add_argument("--final", action="store_true", help="Render a final high-quality MP4 after the preview succeeds.")
    parser.add_argument("--provider", help="LLM provider: deepseek, openrouter, or vllm.")
    parser.add_argument("--model", help="Override the provider's default model.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show each pipeline stage as it runs.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    prompt = args.prompt or input("What animation do you want to create? ")
    state = create_math_animation(prompt, render_final=args.final, provider=args.provider, model=args.model)
    print(f"Model: {state.llm_provider}/{state.llm_model}")
    print(f"Status: {state.status}")
    print(f"Project: generated_projects/{state.project_id}")
    print(f"Draft editor: proofmotion-preview generated_projects/{state.project_id}")
    if state.preview_file:
        print(f"Preview: {state.preview_file}")
    if state.video_file:
        print(f"Final video: {state.video_file}")
    if state.render_errors:
        print("Errors:\n" + "\n".join(state.render_errors))
