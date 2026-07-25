"""Tiny local storyboard editor for draft projects, with no new web dependency."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tools.code_validator import validate_generated_code
from tools.manim_renderer import render_manim_scene


def serve(project_dir: Path, port: int = 8765) -> None:
    storyboard_path = project_dir / "storyboard.json"
    code_path = project_dir / "generated_scene.py"
    preview_dir = project_dir / "preview"

    def latest_preview() -> Path | None:
        videos = list(preview_dir.rglob("*.mp4"))
        return videos[0] if videos else None

    class Handler(BaseHTTPRequestHandler):
        def _json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/api/storyboard":
                self._json(200, json.loads(storyboard_path.read_text(encoding="utf-8")))
                return
            if self.path == "/api/code":
                body = code_path.read_bytes()
                self.send_response(200); self.send_header("Content-Type", "text/plain; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                return
            if self.path == "/preview.mp4":
                video = latest_preview()
                if not video: self.send_error(404, "No preview has been rendered yet"); return
                body = video.read_bytes()
                self.send_response(200); self.send_header("Content-Type", "video/mp4"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                return
            if self.path == "/":
                page = b'''<!doctype html><title>Math Manim Draft Editor</title><style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem;background:#101622;color:#eaf0ff}textarea{width:100%;height:34vh;background:#172238;color:#eaf0ff;border:1px solid #557;padding:1rem;font:13px ui-monospace,monospace}button{margin:.8rem .5rem .8rem 0;padding:.6rem 1rem}video{width:100%;background:#000}</style><h1>Math Manim live draft editor</h1><p>Change the storyboard for review. Edit Manim code and render a fresh low-quality preview before authorizing a final MP4.</p><h2>Storyboard</h2><textarea id="storyboard"></textarea><br><button onclick="saveStoryboard()">Save storyboard</button><h2>Generated Manim code</h2><textarea id="code"></textarea><br><button onclick="renderDraft()">Save and render draft</button><span id="status"></span><h2>Current preview</h2><video id="video" controls src="/preview.mp4"></video><script>const status=document.querySelector('#status');fetch('/api/storyboard').then(r=>r.json()).then(x=>storyboard.value=JSON.stringify(x,null,2));fetch('/api/code').then(r=>r.text()).then(x=>code.value=x);async function saveStoryboard(){let r=await fetch('/api/storyboard',{method:'POST',body:storyboard.value});status.textContent=r.ok?'Storyboard saved.':'Invalid storyboard.'}async function renderDraft(){status.textContent='Rendering draft...';let r=await fetch('/api/code',{method:'POST',body:code.value});let x=await r.json();status.textContent=x.ok?'Draft ready.':'Render failed: '+x.error;if(x.ok){video.src='/preview.mp4?'+Date.now();video.load();}}</script>'''
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Content-Length", str(len(page))); self.end_headers(); self.wfile.write(page)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            if self.path == "/api/storyboard":
                try:
                    size = int(self.headers.get("Content-Length", "0")); value = json.loads(self.rfile.read(size))
                    if not isinstance(value, dict) or "scenes" not in value: raise ValueError("Storyboard needs scenes")
                    storyboard_path.write_text(json.dumps(value, indent=2), encoding="utf-8")
                    self._json(200, {"saved": True}); return
                except (ValueError, json.JSONDecodeError) as error:
                    self._json(400, {"saved": False, "error": str(error)}); return
            if self.path == "/api/code":
                code = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8")
                valid, error = validate_generated_code(code)
                if not valid: self._json(400, {"ok": False, "error": error}); return
                code_path.write_text(code, encoding="utf-8")
                result = render_manim_scene(code_path, preview_dir, quality="l", timeout_seconds=90)
                self._json(200 if result.returncode == 0 else 400, {"ok": result.returncode == 0, "error": result.stderr[-3000:]})
                return
            self.send_error(404)

    print(f"Draft editor: http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve(args.project_dir, args.port)
