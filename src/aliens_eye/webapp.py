"""Small web dashboard for Aliens Eye.

Runs the existing CLI engine in a subprocess so the web UI stays isolated from
scanner internals and the terminal interface keeps working unchanged.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from aiohttp import web

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aliens Eye Web</title>
<style>
:root{color-scheme:dark;--bg:#060912;--panel:#0e1424;--panel2:#131b30;--text:#eef3ff;--muted:#8e9ab5;--accent:#78ffcb;--accent2:#7ea6ff;--danger:#ff7185;--line:#24304c}
*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:radial-gradient(circle at 20% -10%,#183451 0,transparent 34%),radial-gradient(circle at 90% 0,#18322b 0,transparent 28%),var(--bg);color:var(--text);min-height:100vh}
.wrap{max-width:1180px;margin:auto;padding:28px}.top{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:28px}.brand{display:flex;align-items:center;gap:14px}.eye{width:50px;height:50px;border:1px solid #31685e;border-radius:16px;display:grid;place-items:center;background:linear-gradient(145deg,#101d2c,#10251f);box-shadow:0 0 28px #30ffb720}.eye:after{content:'◉';font-size:27px;color:var(--accent)}h1{font-size:22px;margin:0}.sub{color:var(--muted);font-size:13px;margin-top:4px}.badge{border:1px solid #315347;background:#0f201c;color:#9cffdc;border-radius:999px;padding:8px 12px;font-size:12px}.hero,.panel{background:#0c1220dd;border:1px solid var(--line);border-radius:20px;box-shadow:0 18px 60px #0006}.hero{padding:24px}.form{display:grid;grid-template-columns:1fr 150px 130px;gap:12px}.input,.select,.btn{height:48px;border-radius:12px;border:1px solid #2a3856;font:inherit}.input,.select{background:#09101e;color:var(--text);padding:0 14px;outline:none}.input:focus,.select:focus{border-color:var(--accent2);box-shadow:0 0 0 3px #7ea6ff18}.btn{background:linear-gradient(135deg,var(--accent),#49cba0);color:#04110d;font-weight:800;cursor:pointer;border:0}.btn:disabled{opacity:.45;cursor:not-allowed}.hint{margin-top:12px;color:var(--muted);font-size:12px}.status{margin-top:18px;display:none;padding:12px 14px;border-radius:12px;background:#0b1720;border:1px solid #20364a;color:#bcd2e8}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0}.stat{padding:17px;background:var(--panel);border:1px solid var(--line);border-radius:16px}.stat b{font-size:27px;display:block}.stat span{color:var(--muted);font-size:12px}.panel{overflow:hidden}.panelHead{padding:17px 19px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}.panelHead strong{font-size:14px}.panelHead span{color:var(--muted);font-size:12px}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:13px 18px;border-bottom:1px solid #1b263d;font-size:13px}th{color:#95a3c3;font-size:11px;text-transform:uppercase;letter-spacing:.08em;background:#0b1120}tr:hover td{background:#11192b}.pill{padding:5px 9px;border-radius:999px;font-size:11px;font-weight:700}.found{background:#103128;color:#87ffd2}.maybe{background:#332b14;color:#ffdf80}.notfound{background:#301923;color:#ff9eac}.link{color:#8fb4ff;text-decoration:none}.empty{padding:46px;text-align:center;color:var(--muted)}.error{color:#ff9eac}
@media(max-width:760px){.wrap{padding:16px}.form{grid-template-columns:1fr}.grid{grid-template-columns:1fr 1fr}.badge{display:none}th:nth-child(4),td:nth-child(4){display:none}th,td{padding:11px 10px}.panel{overflow-x:auto}}
</style>
</head>
<body><main class="wrap">
<div class="top"><div class="brand"><div class="eye"></div><div><h1>ALIENS EYE WEB</h1><div class="sub">Public username OSINT dashboard</div></div></div><div class="badge">Web Preview · local-first</div></div>
<section class="hero">
<form id="scanForm" class="form">
<input id="username" class="input" autocomplete="off" maxlength="64" placeholder="Enter a public username, e.g. octocat" required>
<select id="profile" class="select"><option value="quick">Quick scan</option><option value="full">Full scan</option><option value="aggressive">Aggressive</option></select>
<button id="scanBtn" class="btn">SCAN</button>
</form>
<div class="hint">Use only for legitimate OSINT research and public information. The web layer invokes the existing Aliens Eye scanner.</div>
<div id="status" class="status"></div>
</section>
<div id="stats" class="grid" style="display:none"></div>
<section class="panel" style="margin-top:18px"><div class="panelHead"><strong>Scan results</strong><span id="summary">No scan yet</span></div><div id="results" class="empty">Enter a username to begin.</div></section>
</main>
<script>
const form=document.getElementById('scanForm'),btn=document.getElementById('scanBtn'),statusBox=document.getElementById('status'),results=document.getElementById('results'),stats=document.getElementById('stats'),summary=document.getElementById('summary');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
function normStatus(v){v=String(v||'').toLowerCase();if(v.includes('found')&&!v.includes('not'))return 'found';if(v.includes('maybe')||v.includes('unknown'))return 'maybe';return 'notfound'}
function render(data){const rows=data.results||[];const found=rows.filter(r=>normStatus(r.status)==='found').length,maybe=rows.filter(r=>normStatus(r.status)==='maybe').length;stats.style.display='grid';stats.innerHTML=`<div class="stat"><b>${rows.length}</b><span>Checked</span></div><div class="stat"><b>${found}</b><span>Found</span></div><div class="stat"><b>${maybe}</b><span>Maybe</span></div><div class="stat"><b>${data.elapsed_seconds??'—'}</b><span>Seconds</span></div>`;summary.textContent=`${esc(data.username)} · ${found} found · ${maybe} maybe`;if(!rows.length){results.className='empty';results.textContent='No result rows were produced.';return}results.className='';results.innerHTML=`<table><thead><tr><th>Site</th><th>Status</th><th>Confidence</th><th>HTTP</th><th>Profile</th></tr></thead><tbody>${rows.sort((a,b)=>(b.confidence||0)-(a.confidence||0)).map(r=>`<tr><td><strong>${esc(r.site)}</strong></td><td><span class="pill ${normStatus(r.status)}">${esc(r.status||'Unknown')}</span></td><td>${esc(r.confidence??'—')}%</td><td>${esc(r.code??'—')}</td><td>${r.url?`<a class="link" href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">Open ↗</a>`:'—'}</td></tr>`).join('')}</tbody></table>`}
form.addEventListener('submit',async e=>{e.preventDefault();const username=document.getElementById('username').value.trim().replace(/^@/,'');const profile=document.getElementById('profile').value;btn.disabled=true;btn.textContent='SCANNING…';statusBox.style.display='block';statusBox.className='status';statusBox.textContent='Scanning public profile locations. Large scans can take a while.';try{const res=await fetch('/api/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,profile})});const data=await res.json();if(!res.ok)throw new Error(data.error||'Scan failed');render(data);statusBox.textContent=`Scan complete for @${username}.`;}catch(err){statusBox.className='status error';statusBox.textContent=err.message;}finally{btn.disabled=false;btn.textContent='SCAN'}});
</script></body></html>"""


def _flatten_report(payload: Any) -> list[dict[str, Any]]:
    """Extract result rows from current and older Aliens Eye JSON shapes."""
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("results", "sites", "scan_results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]

    rows: list[dict[str, Any]] = []
    for value in payload.values():
        if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
            rows.extend(value)
    return rows


async def index(_: web.Request) -> web.Response:
    return web.Response(text=PAGE, content_type="text/html")


async def health(_: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "aliens-eye-web"})


async def scan(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body."}, status=400)

    username = str(body.get("username", "")).strip().lstrip("@")
    profile = str(body.get("profile", "quick")).lower()
    if not USERNAME_RE.fullmatch(username):
        return web.json_response(
            {"error": "Username must be 1-64 characters using letters, numbers, _, . or -."},
            status=400,
        )
    if profile not in {"quick", "full", "aggressive"}:
        profile = "quick"

    loop = asyncio.get_running_loop()
    started = loop.time()
    with tempfile.TemporaryDirectory(prefix="aliens-eye-web-") as temp_dir:
        cmd = [
            sys.executable,
            "-m",
            "aliens_eye",
            username,
            "--plain",
            "--profile",
            profile,
            "--format",
            "json",
            "--output",
            temp_dir,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return web.json_response({"error": "Scan timed out after 180 seconds."}, status=504)

        if proc.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            if not detail:
                detail = stdout.decode("utf-8", errors="replace").strip()
            return web.json_response(
                {"error": "Aliens Eye scanner failed.", "detail": detail[-1500:]}, status=500
            )

        reports = sorted(Path(temp_dir).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not reports:
            return web.json_response(
                {"error": "Scanner completed but did not produce a JSON report."}, status=500
            )
        try:
            payload = json.loads(reports[0].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return web.json_response({"error": f"Could not read scan report: {exc}"}, status=500)

    rows = _flatten_report(payload)
    safe_rows = []
    for row in rows:
        safe_rows.append(
            {
                "site": row.get("site", "Unknown"),
                "status": row.get("status", "Unknown"),
                "confidence": row.get("confidence", 0),
                "code": row.get("code", row.get("http_status", 0)),
                "url": row.get("final_url") or row.get("url") or "",
                "response_time": row.get("response_time"),
            }
        )

    return web.json_response(
        {
            "username": username,
            "profile": profile,
            "elapsed_seconds": round(loop.time() - started, 2),
            "results": safe_rows,
        }
    )


def create_app() -> web.Application:
    app = web.Application(client_max_size=64 * 1024)
    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    app.router.add_post("/api/scan", scan)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Aliens Eye local web dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    web.run_app(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
