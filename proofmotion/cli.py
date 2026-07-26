import argparse
import logging
import sys
import time

from proofmotion.pipeline import create_math_animation

SUCCESS_STATUSES = {"preview_ready", "final_ready"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan, verify, preview, and render mathematical Manim animations.")
    parser.add_argument("prompt", nargs="?", help="Mathematical animation request")
    parser.add_argument("--final", action="store_true", help="Render a final high-quality MP4 after the preview succeeds.")
    parser.add_argument("--provider", help="LLM provider: deepseek, openai, openrouter, or vllm.")
    parser.add_argument("--model", help="Override the provider's default model.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show each pipeline stage as it runs.")
    parser.add_argument("--live", action="store_true", help="Watch the run in a browser as it happens.")
    parser.add_argument("--live-port", type=int, default=8770)
    parser.add_argument("--live-host", default="127.0.0.1", help="Use 0.0.0.0 to watch from another machine.")
    parser.add_argument("--open-browser", action="store_true", help="Try to launch a browser (off by default; fails over SSH).")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    prompt = args.prompt or input("What animation do you want to create? ")

    bus = None
    if args.live:
        from proofmotion.runtime.events import BUS
        from proofmotion.web.live import serve_live

        bus = BUS
        serve_live(port=args.live_port, host=args.live_host, open_browser=args.open_browser)
        # Deliberately no prompt here. Blocking on input() suspends the job if
        # stdin is not an interactive terminal, and it is unnecessary: the event
        # bus replays the whole run to whoever connects, however late.
        time.sleep(2)

    try:
        state = create_math_animation(
            prompt, render_final=args.final, provider=args.provider,
            model=args.model,
        )
    except Exception as error:
        if bus:
            bus.emit("done", ok=False, status=f"{type(error).__name__}: {error}")
        raise
    if bus:
        bus.emit("done", ok=state.status in SUCCESS_STATUSES, status=state.status)

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

    if args.live:
        # The server is a daemon thread, so keep the process alive to leave the
        # finished run inspectable. Only prompt on a real terminal; reading stdin
        # from a non-interactive one suspends the job instead of waiting.
        try:
            if sys.stdin.isatty():
                input("\nLive view still running. Press Enter to exit... ")
            else:
                print("\nLive view still running. Ctrl-C to exit.", flush=True)
                while True:
                    time.sleep(3600)
        except (KeyboardInterrupt, EOFError):
            pass
