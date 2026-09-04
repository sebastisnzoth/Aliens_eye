"""Vercel-compatible web entrypoint for Aliens Eye."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flask import Flask, jsonify, request

from aliens_eye.webapp import PAGE, USERNAME_RE, _flatten_report

app = Flask(__name__)

# Hosted scans must finish inside Vercel's serverless execution window. These
# presets intentionally target useful, high-signal public platforms rather than
# the entire 840+ site catalog. Full catalog scans remain available locally via
# the CLI / aliens_eye_web command.
HOSTED_SITE_PRESETS = {
    "quick": [
        "github", "gitlab", "reddit", "telegram", "vimeo", "imgur",
        "unsplash", "producthunt", "sourceforge", "codewars", "codechef",
        "fandom", "instructables", "speedrun", "researchgate",
    ],
    "full": [
        "github", "gitlab", "reddit", "telegram", "vimeo", "imgur",
        "unsplash", "producthunt", "sourceforge", "codewars", "codechef",
        "fandom", "instructables", "speedrun", "researchgate", "myspace",
        "giphy", "mastodon", "medium", "dev.to", "behance", "dribbble",
        "pinterest", "twitch", "soundcloud", "spotify",
    ],
    "aggressive": [
        "github", "gitlab", "reddit", "telegram", "vimeo", "imgur",
        "unsplash", "producthunt", "sourceforge", "codewars", "codechef",
        "fandom", "instructables", "speedrun", "researchgate", "myspace",
        "giphy", "mastodon", "medium", "dev.to", "behance", "dribbble",
        "pinterest", "twitch", "soundcloud", "spotify", "youtube", "steam",
        "keybase", "about.me", "gravatar", "replit", "hackernews",
    ],
}


@app.get("/")
def index():
    return PAGE, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "aliens-eye-web", "mode": "hosted-fast-scan"})


@app.post("/api/scan")
def scan():
    body = request.get_json(silent=True) or {}
    username = str(body.get("username", "")).strip().lstrip("@")
    profile = str(body.get("profile", "quick")).lower()

    if not USERNAME_RE.fullmatch(username):
        return jsonify({
            "error": "Username must be 1-64 characters using letters, numbers, _, . or -."
        }), 400

    if profile not in HOSTED_SITE_PRESETS:
        profile = "quick"

    sites = ",".join(HOSTED_SITE_PRESETS[profile])
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="aliens-eye-web-") as temp_dir:
        cmd = [
            sys.executable,
            "-m",
            "aliens_eye",
            username,
            "--plain",
            "--profile",
            "quick",
            "--site",
            sites,
            "--timeout",
            "3.5",
            "--retries",
            "0",
            "--concurrent",
            "20",
            "--rate-limit",
            "0",
            "--format",
            "json",
            "--output",
            temp_dir,
        ]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC) + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45, env=env)
        except subprocess.TimeoutExpired:
            return jsonify({
                "error": "Hosted scan exceeded the serverless limit. Try Quick scan or run the full scanner locally.",
                "hosted_mode": True,
            }), 504

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            return jsonify({"error": "Aliens Eye scanner failed.", "detail": detail[-1500:]}), 500

        reports = sorted(Path(temp_dir).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not reports:
            return jsonify({"error": "Scanner completed but did not produce a JSON report."}), 500

        try:
            payload = json.loads(reports[0].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return jsonify({"error": f"Could not read scan report: {exc}"}), 500

    rows = _flatten_report(payload)
    safe_rows = [
        {
            "site": row.get("site", "Unknown"),
            "status": row.get("status", "Unknown"),
            "confidence": row.get("confidence", 0),
            "code": row.get("code", row.get("http_status", 0)),
            "url": row.get("final_url") or row.get("url") or "",
            "response_time": row.get("response_time"),
        }
        for row in rows
    ]

    return jsonify({
        "username": username,
        "profile": profile,
        "hosted_mode": True,
        "sites_requested": len(HOSTED_SITE_PRESETS[profile]),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "results": safe_rows,
    })
