"""The studio: projects on the left, a conversation in the middle, the film on the right.

A conversation is the right shape because making an explanation is one — you
watch a bit, you say what is wrong, it changes. What makes that bearable is
underneath: a turn edits slides, only edited slides render again, and the clips
are joined by copy.

Everything is served from this file with no build step and no external requests,
matching the existing live view. Progress is streamed while a turn runs, because
a turn takes tens of seconds and showing nothing for that long reads as a hang
rather than as work.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from proofmotion.runtime.events import BUS, headline
from proofmotion.studio.document import Project
from proofmotion.studio.operations import Operation, apply_all, touched
from proofmotion.studio.render import build

log = logging.getLogger(__name__)

PAGE = """<!doctype html>
<meta charset="utf-8"><title>ProofMotion Studio</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--rail:#0a0e14;--line:#26303d;--ink:#e6edf3;--dim:#8b949e;--accent:#4aa3df}
*{box-sizing:border-box}
body{margin:0;height:100vh;display:flex;font:14px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink);overflow:hidden}
#rail{width:212px;flex:none;background:var(--rail);border-right:1px solid var(--line);display:flex;flex-direction:column}
#rail h1{font-size:13px;letter-spacing:.5px;margin:0;padding:15px 14px;color:var(--dim)}
#new{margin:0 12px 10px;padding:9px;border-radius:8px;background:var(--accent);color:#04121e;font-weight:600;border:0;cursor:pointer}
#projects{flex:1;overflow-y:auto;padding:0 8px 10px}
.proj{padding:8px 10px;border-radius:7px;cursor:pointer;font-size:13px;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.proj:hover{background:var(--panel)}
.proj.on{background:var(--panel);color:var(--ink);border-left:2px solid var(--accent)}
.proj small{display:block;font-size:11px;opacity:.65}
#chat{width:37%;min-width:320px;display:flex;flex-direction:column;border-right:1px solid var(--line)}
#log{flex:1;overflow-y:auto;padding:18px}
.msg{margin-bottom:15px;max-width:93%}
.msg.you{margin-left:auto}
.bubble{padding:10px 13px;border-radius:12px;white-space:pre-wrap}
.you .bubble{background:#1f6feb;color:#fff}
.bot .bubble{background:var(--panel);border:1px solid var(--line)}
.tick .bubble{background:none;border:0;color:var(--dim);font-size:12.5px;padding:3px 4px}
.ops{margin-top:6px;font-size:12px;color:var(--dim)}
.ops code{background:#0b1017;padding:1px 5px;border-radius:4px;color:var(--accent)}
#composer{border-top:1px solid var(--line);padding:12px;display:flex;gap:8px}
#q{flex:1;resize:none;background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:9px;padding:10px;font:inherit}
button{background:var(--accent);color:#04121e;border:0;border-radius:9px;padding:0 15px;font-weight:600;cursor:pointer}
button:disabled{opacity:.4;cursor:default}
#right{flex:1;display:flex;flex-direction:column;min-width:0}
#stage{background:#000;display:flex;align-items:center;justify-content:center;padding:6px}
video{max-width:100%;max-height:46vh;width:auto;height:auto;display:block}
#status{padding:8px 14px;font-size:12px;color:var(--dim);border-top:1px solid var(--line);border-bottom:1px solid var(--line);min-height:32px}
#deck{flex:1;overflow-y:auto;padding:13px}
.slide{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:10px 12px;margin-bottom:9px}
.slide.locked{border-color:#8957e5}
.slide h4{margin:0 0 3px;font-size:13px}
.meta{font-size:12px;color:var(--dim)}
.row{display:flex;gap:8px;align-items:center;margin-top:6px;flex-wrap:wrap}
.row label{font-size:12px;color:var(--dim);min-width:80px}
.row input[type=range]{flex:1;min-width:90px}
.row input[type=number],.row input[type=text],.row select,.remake{background:#0b1017;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:4px 7px;font:inherit;max-width:170px}
.remake{flex:1;max-width:none}
.pill{font-size:11px;border:1px solid var(--line);border-radius:20px;padding:2px 10px;color:var(--dim);cursor:pointer;background:none;font-weight:400}
.pill:hover{color:var(--ink);border-color:var(--accent)}
</style>
<div id="rail">
  <h1>PROOFMOTION</h1>
  <button id="new">+ New chat</button>
  <div id="projects"></div>
</div>
<div id="chat">
  <div id="log"></div>
  <div id="composer">
    <textarea id="q" rows="2" placeholder="Show how the area under x^2 is built from rectangles..."></textarea>
    <button id="send">Send</button>
  </div>
</div>
<div id="right">
  <div id="stage"><video id="v" controls></video></div>
  <div id="status">Ready.</div>
  <div id="deck"></div>
</div>
<script>
const $=s=>document.querySelector(s), log=$('#log'), deck=$('#deck'), v=$('#v'),
      status=$('#status'), q=$('#q'), send=$('#send'), projects=$('#projects');
let busy=false, ticks=[];

function bubble(who,text,ops){
  const d=document.createElement('div'); d.className='msg '+who;
  const b=document.createElement('div'); b.className='bubble'; b.textContent=text; d.appendChild(b);
  if(ops&&ops.length){const o=document.createElement('div');o.className='ops';
    o.innerHTML=ops.map(x=>`<code>${x.kind}</code> ${x.reason||''}`).join('<br>');d.appendChild(o);}
  log.appendChild(d); log.scrollTop=log.scrollHeight; return d;
}
function tick(text){                     // transient progress, cleared each turn
  const d=bubble('tick',text); ticks.push(d);
}
function clearTicks(){ ticks.forEach(d=>d.remove()); ticks=[]; }

function control(slide,name,spec){
  const row=document.createElement('div'); row.className='row';
  const lab=document.createElement('label'); lab.textContent=name; row.appendChild(lab);
  const cur=slide.parameters[name]; let input;
  if(spec.enum){ input=document.createElement('select');
    spec.enum.forEach(o=>{const e=document.createElement('option');e.value=e.textContent=o;input.appendChild(e);});
    input.value=cur;
  } else if(spec.type==='number'||spec.type==='integer'){
    const lo=spec.minimum??spec.exclusiveMinimum, hi=spec.maximum??spec.exclusiveMaximum;
    input=document.createElement('input');
    if(lo!==undefined&&hi!==undefined){ input.type='range'; input.min=lo; input.max=hi;
      input.step=spec.type==='integer'?1:(hi-lo)/100; }
    else input.type='number';
    input.value=cur;
  } else if(spec.type==='boolean'){ input=document.createElement('input'); input.type='checkbox'; input.checked=!!cur; }
  else { input=document.createElement('input'); input.type='text'; input.value=cur??''; }
  const out=document.createElement('span'); out.className='meta'; out.textContent=cur;
  input.oninput=()=>out.textContent=input.type==='checkbox'?input.checked:input.value;
  input.onchange=()=>{ let value=input.type==='checkbox'?input.checked:input.value;
    if(spec.type==='number') value=parseFloat(value);
    if(spec.type==='integer') value=parseInt(value,10);
    post('/api/parameter',{slide_id:slide.id,name,value}); };
  row.appendChild(input); row.appendChild(out); return row;
}

function draw(s){
  if(s.projects) drawProjects(s);
  deck.innerHTML='';
  (s.slides||[]).forEach(sl=>{
    const d=document.createElement('div'); d.className='slide'+(sl.locked?' locked':'');
    d.innerHTML=`<h4>${sl.title||'(untitled)'}</h4><div class="meta">${sl.id} · ${sl.component||'text only'} · ${sl.seconds}s${sl.locked?' · locked':''}</div>`;
    const schema=(s.schemas||{})[sl.component]||{};
    Object.entries(schema).forEach(([n,spec])=>{ if(n in sl.parameters) d.appendChild(control(sl,n,spec)); });
    ['title','caption','built.group'].forEach(what=>{
      const cur=((sl.overrides||{}).shift||{})[what]||{dx:0,dy:0};
      const row=document.createElement('div'); row.className='row';
      const lab=document.createElement('label'); lab.textContent='move '+what.replace('built.group','figure');
      row.appendChild(lab);
      ['dx','dy'].forEach(axis=>{
        const i=document.createElement('input'); i.type='range'; i.min=-3; i.max=3; i.step=0.05;
        i.value=cur[axis]||0; i.title=axis;
        const out=document.createElement('span'); out.className='meta'; out.textContent=axis+' '+(cur[axis]||0);
        i.oninput=()=>out.textContent=axis+' '+i.value;
        i.onchange=()=>{ const shift={dx:+cur.dx||0, dy:+cur.dy||0}; shift[axis]=parseFloat(i.value);
          post('/api/nudge',{slide_id:sl.id,name:what,value:{shift}}); };
        row.appendChild(i); row.appendChild(out);
      });
      d.appendChild(row);
    });
    const redo=document.createElement('div'); redo.className='row';
    const box=document.createElement('input'); box.className='remake'; box.type='text';
    box.placeholder='remake this slide: what should change?';
    box.onkeydown=e=>{ if(e.key==='Enter'&&box.value.trim()){
      bubble('you','↻ '+sl.id+': '+box.value.trim());
      post('/api/remake',{slide_id:sl.id,instruction:box.value.trim()}); box.value=''; } };
    redo.appendChild(box); d.appendChild(redo);
    const bar=document.createElement('div'); bar.className='row';
    bar.appendChild(pill(sl.locked?'unlock':'lock',()=>post('/api/lock',{slide_id:sl.id,locked:!sl.locked})));
    bar.appendChild(pill('delete',()=>{ if(confirm('Delete '+sl.id+'?')) post('/api/delete',{slide_id:sl.id}); }));
    d.appendChild(bar); deck.appendChild(d);
  });
  if(s.status) status.textContent=s.status;
  if(s.video){ const t=v.currentTime;
    v.src=s.video+'?r='+s.revision; v.load();
    v.onloadedmetadata=()=>{ if(t&&t<v.duration) v.currentTime=t; };
  } else { v.removeAttribute('src'); v.load(); }
}
function pill(text,fn){ const b=document.createElement('button'); b.className='pill'; b.textContent=text; b.onclick=fn; return b; }

function drawProjects(s){
  projects.innerHTML='';
  s.projects.forEach(p=>{
    const d=document.createElement('div'); d.className='proj'+(p.id===s.project_id?' on':'');
    d.innerHTML=`${p.title||'Untitled'}<small>${p.slides} slides · ${p.when}</small>`;
    d.onclick=()=>{ if(p.id!==s.project_id) post('/api/open',{id:p.id},true); };
    projects.appendChild(d);
  });
}

async function post(path,body,replaceLog){
  if(busy) return; busy=true; send.disabled=true; clearTicks();
  try{
    const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json();
    clearTicks();
    if(replaceLog){ log.innerHTML=''; (j.transcript||[]).forEach(m=>bubble(m.who,m.text,m.operations)); }
    if(j.reply) bubble('bot',j.reply,j.operations);
    if(j.error) bubble('bot','⚠ '+j.error);
    (j.refused||[]).forEach(x=>bubble('bot','⚠ '+x.problem));
    draw(j);
  }catch(e){ clearTicks(); bubble('bot','⚠ '+e); }
  finally{ busy=false; send.disabled=false; }
}

send.onclick=()=>{ const t=q.value.trim(); if(!t||busy) return; bubble('you',t); q.value=''; post('/api/message',{message:t}); };
q.onkeydown=e=>{ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send.onclick();} };
$('#new').onclick=()=>{ log.innerHTML=''; post('/api/new',{},true); };

new EventSource('/events').onmessage=e=>{
  const d=JSON.parse(e.data);
  if(d.kind==='headline'){ status.textContent=d.data.text; if(busy) tick(d.data.text); }
  else if(d.kind==='tool'&&busy) status.textContent='· '+d.data.name;
};
fetch('/api/state').then(r=>r.json()).then(s=>{ (s.transcript||[]).forEach(m=>bubble(m.who,m.text,m.operations)); draw(s); });
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
            ref = (prop.get("allOf") or [{}])[0].get("$ref") or prop.get("$ref")
            if ref:
                resolved.update(defs.get(ref.rsplit("/", 1)[-1], {}))
            fields[field] = resolved
        out[name] = fields
    return out


def _new_id() -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"


class Studio:
    """Many projects under one root, one of them current."""

    def __init__(self, root: Path, client: Any) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.client = client
        self.lock = threading.Lock()
        # A fresh project, not the last one worked on. Resuming looked
        # thrifty — the clips are all cached, so it costs nothing — but it
        # means launching drops you into yesterday's deck, and the first slide
        # you add comes back as s14. Every earlier project is one click away
        # in the explorer, and an untouched new one is never written to disk,
        # so nothing accumulates from simply starting up.
        self.current = _new_id()
        self.status = "Ready."
        self.video = ""

    # ---- projects -------------------------------------------------------

    def _latest(self) -> str | None:
        found = sorted(
            (p for p in self.root.iterdir() if (p / "project.json").is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return found[0].name if found else None

    def directory(self, project_id: str | None = None) -> Path:
        return self.root / (project_id or self.current)

    def listing(self) -> list[dict[str, Any]]:
        out = []
        for path in sorted(self.root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            document = path / "project.json"
            if not document.is_file():
                continue
            try:
                raw = json.loads(document.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            out.append({
                "id": path.name,
                "title": (raw.get("question") or "Untitled")[:52],
                "slides": len(raw.get("slides") or []),
                "when": (raw.get("created_at") or "")[:10],
            })
        return out

    # ---- the current project -------------------------------------------

    def load(self) -> Project:
        try:
            return Project.load(self.directory())
        except Exception:  # noqa: BLE001 - a project that does not exist yet is normal
            return Project.create(self.current, "")

    def transcript(self) -> list[dict[str, Any]]:
        """What was said in this project, so switching back shows the thread."""
        path = self.directory() / "transcript.json"
        if not path.is_file():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    def remember(self, who: str, text: str, operations: list | None = None) -> None:
        path = self.directory() / "transcript.json"
        thread = self.transcript()
        thread.append({"who": who, "text": text, "operations": operations or []})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(thread[-80:], default=str), encoding="utf-8")

    def snapshot(self, project: Project, **extra: Any) -> dict[str, Any]:
        return {
            "project_id": self.current,
            "revision": project.revision,
            "slides": [s.model_dump() for s in project.slides],
            "schemas": _schemas(),
            "projects": self.listing(),
            "video": "/video.mp4" if self.video else "",
            "status": self.status,
            **extra,
        }

    def rebuild(self, project: Project, only: list[str] | None = None) -> dict[str, Any]:
        if not project.slides:
            self.status, self.video = "No slides yet.", ""
            return {}
        report = build(project, self.directory(), only=only)
        self.video = report.get("video", "")
        summary = (
            f"{len(project.slides)} slides · {report['rendered']} rendered, "
            f"{report['reused']} reused · {report.get('seconds', 0)}s"
        )
        if report["failed"]:
            first = report["problems"][0]
            # The reason, not just the slide. "1 failed on s1" tells nobody
            # anything they can act on, and the reason was already in hand.
            reason = " ".join(str(first["error"]).split())[:180]
            summary += f" · {report['failed']} failed on {','.join(first['slides'])}: {reason}"
        self.status = summary
        headline(summary)
        return report


def serve_studio(root: Path, client: Any, *, port: int = 8780, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    """Serve the studio over a root directory of projects."""
    root = Path(root)
    # Pointed at a project rather than a root, treat its parent as the root so
    # the explorer still shows its siblings.
    if (root / "project.json").is_file():
        studio = Studio(root.parent, client)
        studio.current = root.name
    else:
        studio = Studio(root, client)

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

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                self._send(200, "text/html; charset=utf-8", PAGE.encode())
            elif path == "/api/state":
                project = studio.load()
                self._json(studio.snapshot(project, transcript=studio.transcript()))
            elif path == "/video.mp4":
                video = Path(studio.video) if studio.video else None
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
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                BUS.unsubscribe(listener)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
            except (json.JSONDecodeError, ValueError):
                self._json({"error": "malformed request"}, 400)
                return

            with studio.lock:
                try:
                    result = self._act(path, body)
                except Exception as error:
                    log.exception("studio action failed")
                    self._json(studio.snapshot(studio.load(), error=str(error)[:400]))
                    return
                self._json(result)

        def _act(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
            from proofmotion.agents.studio import propose
            from proofmotion.studio.compose_full import answer_fully, draw_by_hand
            from proofmotion.studio.operations import Edit

            if path == "/api/new":
                studio.current = _new_id()
                studio.directory().mkdir(parents=True, exist_ok=True)
                studio.status, studio.video = "New project. Ask a question.", ""
                project = Project.create(studio.current, "")
                project.save(studio.directory())
                return studio.snapshot(project, transcript=[])

            if path == "/api/open":
                wanted = body.get("id") or ""
                if not (studio.root / wanted / "project.json").is_file():
                    return studio.snapshot(studio.load(), error=f"no project {wanted!r}")
                studio.current = wanted
                project = studio.load()
                studio.video, studio.status = "", f"{len(project.slides)} slides."
                # Rebuilding is free when nothing changed: every clip is cached,
                # so reopening a project costs a concat and no renders at all.
                studio.rebuild(project)
                return studio.snapshot(project, transcript=studio.transcript())

            project = studio.load()

            if path in ("/api/message", "/api/remake"):
                if path == "/api/message":
                    message = (body.get("message") or "").strip()
                    if not message:
                        return studio.snapshot(project, error="say something")
                    if not project.question:
                        project.question = message
                    studio.remember("you", message)
                else:
                    slide_id = body.get("slide_id") or ""
                    instruction = (body.get("instruction") or "").strip()
                    if not instruction:
                        return studio.snapshot(project, error="say what should change")
                    project.slide(slide_id)  # raises with a clear message if it is gone
                    message = (
                        f"Change only slide {slide_id}. Leave every other slide exactly as it is. "
                        f"What to change: {instruction}"
                    )
                    studio.remember("you", f"↻ {slide_id}: {instruction}")

                # An opening question gets the whole pipeline: read it, derive
                # the mathematics with symbolic tools, verify, storyboard, and
                # map every scene onto a component. The edit agent answers an
                # opening question with one slide, and one slide is not an
                # explanation. After that the deck exists and edits are edits.
                if not project.slides:
                    operations, reply = answer_fully(studio.client, project, message)
                    if operations:
                        edit = Edit(operations=operations, reply=reply)
                    else:
                        # Nothing to derive, or nothing came of it. A request to
                        # animate something has no mathematics behind it, and
                        # forcing the pipeline through anyway produced eight
                        # verified steps and ten slides that drew nothing.
                        headline("Designing scenes for it")
                        edit = propose(studio.client, project, message)
                        if edit.needs_hand_drawn:
                            operations, reply = draw_by_hand(studio.client, edit.needs_hand_drawn)
                            edit = Edit(operations=operations, reply=reply)
                        elif not edit.operations:
                            # The catalogue is finite and the agent said so.
                            # Refusing is honest and useless; the coder draws it.
                            operations, reply = draw_by_hand(studio.client, message)
                            edit = Edit(operations=operations, reply=reply)
                else:
                    headline("Thinking about what to change")
                    edit = propose(studio.client, project, message)
                    if edit.needs_hand_drawn:
                        # Honoured on an existing deck too. It was only checked
                        # when the deck was empty, so on a deck with slides the
                        # agent raised the flag, nothing read it, and its reply
                        # went out unchanged: "I'll flag this for a hand-drawn
                        # scene" — four times in a row, to someone asking four
                        # times for the same drawing.
                        operations, reply = draw_by_hand(
                            studio.client, edit.needs_hand_drawn, existing=edit.operations,
                        )
                        edit = Edit(operations=operations, reply=reply)
                    elif edit.needs_full_derivation and path == "/api/message":
                        # The ask needs mathematics worked out, not a slide
                        # tweaked. A tweak agent inventing derivations is how a
                        # deck becomes confident and wrong.
                        headline("This needs working out; running the full pipeline")
                        operations, reply = answer_fully(studio.client, project, message)
                        edit = Edit(operations=operations, reply=reply)
                    elif edit.needs_full_derivation:
                        # Escalating from a remake box loses the one thing that
                        # box means. Asked "how do we find pi?" on slide 4, it
                        # derived pi and appended nine slides about Monte Carlo
                        # to the end of a deck about a ramp — every operation
                        # valid, the slide untouched, the deck ruined.
                        return studio.snapshot(project, reply=(
                            "That needs working out from scratch rather than editing this slide. "
                            "Ask it in the main box to add it here, or start a new chat for a "
                            "separate explanation."
                        ))
                outcome = apply_all(project, edit.operations)
                project.save(studio.directory())
                studio.rebuild(project, only=touched(edit.operations))
                reply = edit.reply or f"Applied {outcome['applied']} change(s)."
                studio.remember("bot", reply, [o.model_dump() for o in edit.operations])
                return studio.snapshot(
                    project,
                    reply=reply,
                    operations=[o.model_dump() for o in edit.operations],
                    refused=outcome["refused"],
                )

            if path == "/api/parameter":
                operation = Operation(
                    kind="set_parameter", slide_id=body["slide_id"],
                    name=body["name"], value=body.get("value"),
                )
            elif path == "/api/nudge":
                operation = Operation(
                    kind="nudge", slide_id=body["slide_id"],
                    name=body.get("name") or "caption", value=body.get("value") or {},
                )
            elif path == "/api/lock":
                operation = Operation(kind="lock", slide_id=body["slide_id"], locked=bool(body.get("locked")))
            elif path == "/api/delete":
                operation = Operation(kind="delete", slide_id=body["slide_id"])
            else:
                return studio.snapshot(project, error="unknown action")

            outcome = apply_all(project, [operation])
            if outcome["refused"]:
                return studio.snapshot(project, error=outcome["refused"][0]["problem"])
            project.save(studio.directory())
            # A lock changes no pixels, so it must not invalidate a clip.
            studio.rebuild(project, only=touched([operation]) if operation.kind != "lock" else [])
            return studio.snapshot(project)

    server = ThreadingHTTPServer((host, port), Handler)
    log.info("studio on http://%s:%s over %s", host, port, root)
    return server
