"""Vercel-compatible web entrypoint for Aliens Eye."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from flask import Flask, jsonify, request

from aliens_eye.webapp import PAGE, USERNAME_RE, _flatten_report

app = Flask(__name__)


@app.get("/")
def index():
    return PAGE, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "aliens-eye-web"})


@app.post("/api/scan")
def scan():
    body = request.get_json(silent=True) or {}
    username = str(body.get("username", "")).strip().lstrip("@")
    profile = str(body.get("profile", "quick")).lower()

    if not USERNAME_RE.fullmatch(username):
        return jsonify({
            "error": "Username must be 1-64 characters using letters, numbers, _, . or -."
        }), 400

    if profile not in {"quick", "full", "aggressive"}:
        profile = "quick"

    started = time.monotonic()
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
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=55)
        except subprocess.TimeoutExpired:
            return jsonify({"error": "Scan timed out in the hosted environment."}), 504

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
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "results": safe_rows,
    })
