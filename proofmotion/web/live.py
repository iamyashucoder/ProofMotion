"""Live run viewer: watch the pipeline think, and watch frames appear.

Serves a single page over server-sent events. No dependencies beyond the
standard library, so it runs anywhere the pipeline runs.
"""

from __future__ import annotations

import json
import queue
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from proofmotion.runtime.events import BUS

PAGE = """<!doctype html>
<meta charset="utf-8"><title>ProofMotion — live</title>
<style>
 :root{--bg:#0c1017;--panel:#141b26;--line:#243044;--ink:#e8eef8;--dim:#8b9bb4;
       --ok:#4ade80;--warn:#fbbf24;--fix:#60a5fa;--bad:#f87171}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,sans-serif}
 header{padding:14px 20px;border-bottom:1px solid var(--line);display:flex;gap:16px;align-items:baseline;flex-wrap:wrap}
 h1{font-size:16px;margin:0;letter-spacing:.02em}
 .meta{color:var(--dim);font-size:12px}
 .wrap{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:1px;background:var(--line)}
 @media(max-width:900px){.wrap{grid-template-columns:1fr}}
 section{background:var(--bg);padding:16px 20px;min-height:0}
 h2{font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--dim);margin:0 0 12px}
 #stages{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}
 .stage{padding:4px 10px;border:1px solid var(--line);border-radius:99px;font-size:12px;color:var(--dim)}
 .stage.run{border-color:var(--fix);color:var(--fix);animation:pulse 1.2s infinite}
 .stage.done{border-color:var(--ok);color:var(--ok)}
 .stage.failed{border-color:var(--bad);color:var(--bad)}
 @keyframes pulse{50%{opacity:.45}}
 .head{padding:9px 12px;border-left:3px solid var(--line);background:var(--panel);margin-bottom:7px;border-radius:0 6px 6px 0}
 .head.improved{border-color:var(--ok)} .head.fixed{border-color:var(--fix)}
 .head.warned{border-color:var(--warn)}
 .head .t{font-size:11px;color:var(--dim);margin-left:8px}
 #tools{max-height:44vh;overflow:auto;font:12px/1.6 ui-monospace,monospace}
 .tool{display:flex;gap:8px;padding:3px 0;border-bottom:1px solid #1a2231}
 .tool .n{color:var(--fix);min-width:172px}
 .tool .a{color:var(--dim);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .tool.failed .n{color:var(--bad)}
 .agent{display:inline-block;font-size:10px;padding:1px 6px;border-radius:3px;background:#1e2a3d;color:var(--dim)}
 #strip{display:flex;gap:8px;flex-wrap:wrap}
 #strip img{width:172px;border:1px solid var(--line);border-radius:5px;display:block}
 video{width:100%;background:#000;border-radius:6px;border:1px solid var(--line)}
 pre{background:var(--panel);padding:12px;border-radius:6px;overflow:auto;max-height:38vh;
     font:11px/1.5 ui-monospace,monospace;color:#cbd5e1;border:1px solid var(--line)}
 .empty{color:var(--dim);font-style:italic}
</style>
<header>
  <h1>ProofMotion</h1>
  <span class="meta" id="prompt">waiting for a run…</span>
  <span class="meta" id="model"></span>
  <span class="meta" id="clock"></span>
</header>
<div id="stages"></div>
<div class="wrap">
  <section>
    <h2>What changed</h2><div id="heads"><p class="empty">nothing yet</p></div>
    <h2 style="margin-top:22px">Tool calls <span id="tc" class="meta"></span></h2><div id="tools"></div>
  </section>
  <section>
    <h2>Rendering</h2><div id="strip"><p class="empty">frames appear as Manim writes them</p></div>
    <video id="vid" controls hidden></video>
    <h2 style="margin-top:22px">Latest artifact</h2><pre id="art" class="empty">—</pre>
  </section>
</div>
<script>
const $=s=>document.querySelector(s);
const ORDER=["understand","plan","verify","storyboard","code","typeset","layout","render","repair"];
const chips={};
ORDER.forEach(n=>{const d=document.createElement("div");d.className="stage";d.textContent=n;
  $("#stages").appendChild(d);chips[n]=d;});
let t0=null,tools=0;
setInterval(()=>{if(t0)$("#clock").textContent=((Date.now()-t0)/1000).toFixed(0)+"s elapsed";},500);

const es=new EventSource("/events");
es.onmessage=e=>{
  const ev=JSON.parse(e.data),d=ev.data;
  if(ev.kind==="run"){t0=Date.now();$("#prompt").textContent='"'+d.prompt+'"';$("#model").textContent=d.model;
    $("#heads").innerHTML="";$("#tools").innerHTML="";$("#strip").innerHTML="";}
  if(ev.kind==="stage"&&chips[d.name])chips[d.name].className="stage "+(d.status==="start"?"run":d.status);
  if(ev.kind==="headline"){
    const el=document.createElement("div");el.className="head "+(d.kind||"info");
    el.innerHTML=esc(d.text)+'<span class="t">'+ev.at+'s</span>';
    $("#heads").appendChild(el);el.scrollIntoView({block:"nearest"});}
  if(ev.kind==="tool"){
    tools++;$("#tc").textContent="("+tools+")";
    const el=document.createElement("div");el.className="tool"+(d.failed?" failed":"");
    el.innerHTML='<span class="agent">'+esc(d.agent||"")+'</span><span class="n">'+esc(d.name)+
                 '</span><span class="a">'+esc(d.arguments||"")+'</span><span class="t">'+d.seconds+'s</span>';
    $("#tools").appendChild(el);$("#tools").scrollTop=1e9;}
  if(ev.kind==="retry"){
    const el=document.createElement("div");el.className="head warned";
    el.innerHTML="retry ("+esc(d.agent)+"): "+esc(d.reason||"");$("#heads").appendChild(el);}
  if(ev.kind==="frame"){
    if($("#strip").querySelector(".empty"))$("#strip").innerHTML="";
    const i=new Image();i.src="data:image/png;base64,"+d.image;i.title="beat "+d.index;
    $("#strip").appendChild(i);i.scrollIntoView({block:"nearest"});}
  if(ev.kind==="video"&&d.path){const v=$("#vid");v.hidden=false;v.src="/video?"+Date.now();v.load();}
  if(ev.kind==="artifact"){
    $("#art").className="";
    $("#art").textContent=typeof d.value==="string"?d.value:JSON.stringify(d.value,null,2);}
  if(ev.kind==="done"){ORDER.forEach(n=>chips[n].classList.remove("run"));
    const el=document.createElement("div");el.className="head "+(d.ok?"improved":"warned");
    el.textContent=(d.ok?"Finished: ":"Ended: ")+d.status;$("#heads").appendChild(el);}
};
function esc(s){return String(s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));}
</script>"""


def serve_live(port: int = 8770, host: str = "127.0.0.1", open_browser: bool = False) -> ThreadingHTTPServer:
    """Start the viewer and return the server, so a caller can shut it down.

    open_browser defaults off on purpose: over SSH, or inside a VS Code terminal,
    webbrowser.open() hands off to a helper that can fail noisily and suspend the
    job. Printing the URL always works.
    """

    class Handler(BaseHTTPRequestHandler):
        # SSE needs HTTP/1.1. Browsers will not stream an EventSource over the
        # 1.0 default — curl -N tolerates it, which is why the raw stream looked
        # fine while the page stayed blank.
        protocol_version = "HTTP/1.1"

        def log_message(self, *args: Any) -> None:  # keep the console for pipeline output
            pass

        def _send(self, status: int, ctype: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = self.path.split("?")[0]
            if path == "/":
                self._send(200, "text/html; charset=utf-8", PAGE.encode())
                return
            if path == "/video":
                latest = next(
                    (e for e in reversed(BUS.history) if e.kind == "video" and e.data.get("path")), None
                )
                video = Path(latest.data["path"]) if latest else None
                if not video or not video.exists():
                    self.send_error(404, "no video yet")
                    return
                self._send(200, "video/mp4", video.read_bytes())
                return
            if path == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                listener = BUS.subscribe()
                try:
                    while True:
                        try:
                            event = listener.get(timeout=15)
                            payload = json.dumps(event.as_dict(), default=str)
                            self.wfile.write(f"data: {payload}\n\n".encode())
                        except queue.Empty:
                            self.wfile.write(b": keep-alive\n\n")  # stop proxies idling us out
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    BUS.unsubscribe(listener)
                return
            self.send_error(404)

    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True, name="live-server").start()

    shown = _lan_ip() if host == "0.0.0.0" else host
    url = f"http://{shown}:{port}"
    print("\n  ┌─ Live view ─────────────────────────────────", flush=True)
    print(f"  │  {url}", flush=True)
    print("  │  Open it any time — the run replays from the start.", flush=True)
    print("  └─────────────────────────────────────────────\n", flush=True)

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception as error:  # noqa: BLE001 - SSH and headless hosts have no browser
            print(f"  (could not open a browser: {error}; use the URL above)", flush=True)
    return server


def _lan_ip() -> str:
    """Address another machine can reach, for --live-host 0.0.0.0."""
    import socket

    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()
