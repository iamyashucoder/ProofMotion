"""The studio: a chat on the left, the deck and the video on the right.

A conversation is the right shape for this because making an explanation is a
conversation — you watch a bit, you say what is wrong, it changes. What makes
that bearable is underneath: a turn edits slides, only edited slides render
again, and the clips are joined by copy. Asking for one more scene costs one
scene.

Everything is served from this file with no build step and no external
requests, matching the existing live view. The page is small enough to read.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from proofmotion.runtime.events import BUS
from proofmotion.studio.document import Project
from proofmotion.studio.operations import apply_all, touched
from proofmotion.studio.render import build

log = logging.getLogger(__name__)

PAGE = """<!doctype html>
<meta charset="utf-8"><title>ProofMotion Studio</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--line:#26303d;--ink:#e6edf3;--dim:#8b949e;--accent:#4aa3df}
*{box-sizing:border-box}
body{margin:0;height:100vh;display:flex;font:14px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink)}
#chat{width:38%;min-width:340px;display:flex;flex-direction:column;border-right:1px solid var(--line)}
#log{flex:1;overflow-y:auto;padding:18px}
.msg{margin-bottom:16px;max-width:92%}
.msg.you{margin-left:auto}
.bubble{padding:10px 13px;border-radius:12px;white-space:pre-wrap}
.you .bubble{background:#1f6feb;color:#fff}
.bot .bubble{background:var(--panel);border:1px solid var(--line)}
.ops{margin-top:6px;font-size:12px;color:var(--dim)}
.ops code{background:#0b1017;padding:1px 5px;border-radius:4px;color:var(--accent)}
#composer{border-top:1px solid var(--line);padding:12px;display:flex;gap:8px}
#q{flex:1;resize:none;background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:9px;padding:10px;font:inherit}
button{background:var(--accent);color:#04121e;border:0;border-radius:9px;padding:0 16px;font-weight:600;cursor:pointer}
button:disabled{opacity:.45;cursor:default}
#right{flex:1;display:flex;flex-direction:column;min-width:0}
video{width:100%;background:#000;max-height:52vh}
#deck{flex:1;overflow-y:auto;padding:14px;border-top:1px solid var(--line)}
.slide{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:10px 12px;margin-bottom:9px}
.slide h4{margin:0 0 4px;font-size:13px}
.slide .meta{font-size:12px;color:var(--dim)}
.slide.locked{border-color:#8957e5}
.row{display:flex;gap:8px;align-items:center;margin-top:7px;flex-wrap:wrap}
.row label{font-size:12px;color:var(--dim);min-width:82px}
.row input[type=range]{flex:1}
.row input[type=number],.row input[type=text],.row select{background:#0b1017;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:3px 6px;font:inherit;max-width:150px}
.pill{font-size:11px;border:1px solid var(--line);border-radius:20px;padding:1px 9px;color:var(--dim);cursor:pointer;background:none}
#status{padding:7px 14px;font-size:12px;color:var(--dim);border-top:1px solid var(--line);min-height:30px}
h3{margin:0;padding:13px 14px;font-size:13px;letter-spacing:.4px;color:var(--dim);border-bottom:1px solid var(--line)}
</style>
<div id="chat">
  <h3>ASK, THEN KEEP ASKING</h3>
  <div id="log"></div>
  <div id="composer">
    <textarea id="q" rows="2" placeholder="Show how the area under x^2 is built from rectangles..."></textarea>
    <button id="send">Send</button>
  </div>
</div>
<div id="right">
  <video id="v" controls></video>
  <div id="status">No slides yet.</div>
  <div id="deck"></div>
</div>
<script>
const log=document.getElementById('log'), deck=document.getElementById('deck'),
      v=document.getElementById('v'), status=document.getElementById('status'),
      q=document.getElementById('q'), send=document.getElementById('send');

function say(who,text,ops){
  const d=document.createElement('div'); d.className='msg '+who;
  const b=document.createElement('div'); b.className='bubble'; b.textContent=text; d.appendChild(b);
  if(ops&&ops.length){const o=document.createElement('div');o.className='ops';
    o.innerHTML=ops.map(x=>`<code>${x.kind}</code> ${x.reason||''}`).join('<br>');d.appendChild(o);}
  log.appendChild(d); log.scrollTop=log.scrollHeight;
}

function control(slide,name,spec){
  const row=document.createElement('div'); row.className='row';
  const lab=document.createElement('label'); lab.textContent=name; row.appendChild(lab);
  const cur=slide.parameters[name];
  let input;
  if(spec.enum){ input=document.createElement('select');
    spec.enum.forEach(o=>{const e=document.createElement('option');e.value=e.textContent=o;input.appendChild(e);});
    input.value=cur;
  } else if(spec.type==='number'||spec.type==='integer'){
    const lo=spec.minimum??spec.exclusiveMinimum, hi=spec.maximum??spec.exclusiveMaximum;
    if(lo!==undefined&&hi!==undefined){ input=document.createElement('input'); input.type='range';
      input.min=lo; input.max=hi; input.step=spec.type==='integer'?1:(hi-lo)/100; input.value=cur;
    } else { input=document.createElement('input'); input.type='number'; input.value=cur; }
  } else if(spec.type==='boolean'){ input=document.createElement('input'); input.type='checkbox'; input.checked=!!cur; }
  else { input=document.createElement('input'); input.type='text'; input.value=cur??''; }
  const out=document.createElement('span'); out.className='meta'; out.textContent=cur;
  input.addEventListener('input',()=>{out.textContent=input.type==='checkbox'?input.checked:input.value;});
  input.addEventListener('change',()=>{
    let value=input.type==='checkbox'?input.checked:input.value;
    if(spec.type==='number') value=parseFloat(value);
    if(spec.type==='integer') value=parseInt(value,10);
    setParam(slide.id,name,value);
  });
  row.appendChild(input); row.appendChild(out);
  return row;
}

function draw(state){
  deck.innerHTML='';
  (state.slides||[]).forEach(s=>{
    const d=document.createElement('div'); d.className='slide'+(s.locked?' locked':'');
    d.innerHTML=`<h4>${s.title||'(untitled)'}</h4>
      <div class="meta">${s.id} · ${s.component||'text only'} · ${s.seconds}s${s.locked?' · locked':''}</div>`;
    const schema=state.schemas[s.component]||{};
    Object.entries(schema).forEach(([n,spec])=>{ if(n in s.parameters) d.appendChild(control(s,n,spec)); });
    const bar=document.createElement('div'); bar.className='row';
    const lock=document.createElement('button'); lock.className='pill';
    lock.textContent=s.locked?'unlock':'lock'; lock.onclick=()=>toggleLock(s.id,!s.locked);
    const del=document.createElement('button'); del.className='pill'; del.textContent='delete';
    del.onclick=()=>{ if(confirm('Delete '+s.id+'?')) remove(s.id); };
    bar.appendChild(lock); bar.appendChild(del); d.appendChild(bar);
    deck.appendChild(d);
  });
  status.textContent=state.status||'';
  if(state.video){ const t=v.currentTime; v.src=state.video+'?r='+state.revision; v.load();
    v.onloadedmetadata=()=>{ if(t<v.duration) v.currentTime=t; }; }
}

async function call(path,body){
  send.disabled=true; status.textContent='Working...';
  try{
    const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json();
    if(j.reply) say('bot',j.reply,j.operations);
    if(j.error) say('bot','⚠ '+j.error);
    draw(j);
  }catch(e){ say('bot','⚠ '+e); }
  finally{ send.disabled=false; }
}
const ask=t=>call('/api/message',{message:t});
const setParam=(id,name,value)=>call('/api/parameter',{slide_id:id,name,value});
const toggleLock=(id,locked)=>call('/api/lock',{slide_id:id,locked});
const remove=id=>call('/api/delete',{slide_id:id});

send.onclick=()=>{ const t=q.value.trim(); if(!t) return; say('you',t); q.value=''; ask(t); };
q.addEventListener('keydown',e=>{ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send.onclick();} });

new EventSource('/events').onmessage=e=>{
  const d=JSON.parse(e.data);
  if(d.kind==='headline'||d.kind==='stage') status.textContent=d.data.text||(d.data.name+' '+(d.data.status||''));
};
fetch('/api/project').then(r=>r.json()).then(draw);
</script>
"""


def _schemas() -> dict[str, dict[str, Any]]:
    """Parameter metadata per component, so the page can build its controls.

    Every component already declares this — types, bounds, and the exact set of
    valid options. The panel is derived from it rather than written per
    component, which is why a slider knows it may not leave the range.
    """
    from proofmotion.components import COMPONENTS

    out: dict[str, dict[str, Any]] = {}
    for name, spec in COMPONENTS.items():
        schema = spec.params.model_json_schema()
        defs = schema.get("$defs", {})
        fields = {}
        for field, prop in (schema.get("properties") or {}).items():
            resolved = dict(prop)
            # Literal fields arrive as a $ref to an enum definition.
            ref = prop.get("allOf", [{}])[0].get("$ref") or prop.get("$ref")
            if ref:
                resolved.update(defs.get(ref.rsplit("/", 1)[-1], {}))
            fields[field] = resolved
        out[name] = fields
    return out


def serve_studio(
    project_dir: Path, client: Any, *, port: int = 8780, host: str = "127.0.0.1"
) -> ThreadingHTTPServer:
    """Serve the studio for one project directory."""
    project_dir = Path(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    state: dict[str, Any] = {"status": "Ready.", "video": ""}

    def load() -> Project:
        try:
            return Project.load(project_dir)
        except Exception:  # noqa: BLE001 - a missing document is the normal first case
            return Project.create(project_dir.name, "")

    def snapshot(project: Project, **extra: Any) -> dict[str, Any]:
        return {
            "project_id": project.project_id,
            "revision": project.revision,
            "slides": [s.model_dump() for s in project.slides],
            "schemas": _schemas(),
            "video": "/video.mp4" if state["video"] else "",
            "status": state["status"],
            **extra,
        }

    def rebuild(project: Project, only: list[str] | None = None) -> dict[str, Any]:
        """Render what changed and join. The only place a video is produced."""
        if not project.slides:
            state.update(status="No slides yet.", video="")
            return {}
        report = build(project, project_dir, only=only)
        state["video"] = report.get("video", "")
        summary = (
            f"{len(project.slides)} slides · {report['rendered']} rendered, "
            f"{report['reused']} reused · {report.get('seconds', 0)}s"
        )
        if report["failed"]:
            summary += f" · {report['failed']} failed: {report['problems'][0]['error'][:120]}"
        state["status"] = summary
        return report

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args: Any) -> None:
            pass

        def _send(self, status: int, ctype: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload: dict[str, Any], status: int = 200) -> None:
            self._send(status, "application/json", json.dumps(payload, default=str).encode())

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                self._send(200, "text/html; charset=utf-8", PAGE.encode())
            elif path == "/api/project":
                self._json(snapshot(load()))
            elif path == "/video.mp4":
                video = Path(state["video"]) if state["video"] else None
                if video and video.is_file():
                    self._send(200, "video/mp4", video.read_bytes())
                else:
                    self._send(404, "text/plain", b"no video yet")
            elif path == "/events":
                self._stream()
            else:
                self._send(404, "text/plain", b"not found")

        def _stream(self) -> None:
            listener: queue.Queue = BUS.subscribe()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                while True:
                    event = listener.get()
                    self.wfile.write(f"data: {json.dumps(event.as_dict(), default=str)}\n\n".encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                BUS.unsubscribe(listener)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                body = self._body()
            except json.JSONDecodeError:
                self._json({"error": "malformed request"}, 400)
                return

            with lock:
                project = load()
                try:
                    result = self._act(path, project, body)
                except Exception as error:
                    log.exception("studio action failed")
                    self._json(snapshot(project, error=str(error)[:400]), 200)
                    return
                project.save(project_dir)
                self._json(snapshot(project, **result))

        def _act(self, path: str, project: Project, body: dict[str, Any]) -> dict[str, Any]:
            from proofmotion.agents.studio import propose
            from proofmotion.studio.operations import Operation

            if path == "/api/message":
                message = (body.get("message") or "").strip()
                if not message:
                    return {"error": "say something"}
                if not project.question:
                    project.question = message
                edit = propose(client, project, message)
                outcome = apply_all(project, edit.operations)
                rebuild(project, only=touched(edit.operations))
                return {
                    "reply": edit.reply or f"Applied {outcome['applied']} change(s).",
                    "operations": [o.model_dump() for o in edit.operations],
                    "refused": outcome["refused"],
                }

            if path == "/api/parameter":
                operation = Operation(
                    kind="set_parameter", slide_id=body["slide_id"],
                    name=body["name"], value=body.get("value"),
                )
            elif path == "/api/lock":
                operation = Operation(kind="lock", slide_id=body["slide_id"], locked=bool(body.get("locked")))
            elif path == "/api/delete":
                operation = Operation(kind="delete", slide_id=body["slide_id"])
            else:
                return {"error": "unknown action"}

            outcome = apply_all(project, [operation])
            if outcome["refused"]:
                return {"error": outcome["refused"][0]["problem"]}
            # A lock changes no pixels, so it must not invalidate a clip.
            rebuild(project, only=touched([operation]) if operation.kind != "lock" else [])
            return {"reply": ""}

    server = ThreadingHTTPServer((host, port), Handler)
    log.info("studio on http://%s:%s", host, port)
    return server
