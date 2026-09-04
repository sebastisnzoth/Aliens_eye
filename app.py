"""Vercel-compatible web entrypoint for Aliens Eye."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flask import Flask, jsonify, request

from aliens_eye.webapp import PAGE, USERNAME_RE

app = Flask(__name__)

SITE_URLS = {
    "github": "https://github.com/{}",
    "gitlab": "https://gitlab.com/{}",
    "reddit": "https://www.reddit.com/user/{}",
    "telegram": "https://t.me/{}",
    "vimeo": "https://vimeo.com/{}",
    "imgur": "https://imgur.com/user/{}",
    "unsplash": "https://unsplash.com/@{}",
    "producthunt": "https://www.producthunt.com/@{}",
    "sourceforge": "https://sourceforge.net/u/{}",
    "codewars": "https://www.codewars.com/users/{}",
    "codechef": "https://www.codechef.com/users/{}",
    "fandom": "https://www.fandom.com/u/{}",
    "instructables": "https://www.instructables.com/member/{}",
    "speedrun": "https://speedrun.com/user/{}",
    "researchgate": "https://www.researchgate.net/profile/{}",
    "myspace": "https://myspace.com/{}",
    "giphy": "https://giphy.com/{}",
    "dev.to": "https://dev.to/{}",
    "dribbble": "https://dribbble.com/{}",
    "soundcloud": "https://soundcloud.com/{}",
    "tiktok": "https://www.tiktok.com/@{}",
    "about.me": "https://about.me/{}",
    "replit": "https://replit.com/@{}",
    "steam": "https://steamcommunity.com/id/{}",
    "youtube": "https://www.youtube.com/@{}",
}

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
        "giphy", "dev.to", "dribbble", "soundcloud", "tiktok",
    ],
    "aggressive": [
        "github", "gitlab", "reddit", "telegram", "vimeo", "imgur",
        "unsplash", "producthunt", "sourceforge", "codewars", "codechef",
        "fandom", "instructables", "speedrun", "researchgate", "myspace",
        "giphy", "dev.to", "dribbble", "soundcloud", "tiktok", "about.me",
        "replit", "steam", "youtube",
    ],
}


def check_site(site: str, username: str) -> dict:
    url = SITE_URLS[site].format(username)
    started = time.monotonic()
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AliensEyeWeb/2.2)",
            "Accept": "text/html,application/xhtml+xml",
        },
        method="GET",
    )
    try:
        with urlopen(req, timeout=4) as resp:
            code = int(getattr(resp, "status", 200) or 200)
            final_url = resp.geturl() or url
            if 200 <= code < 300:
                status = "Found"
                confidence = 70
            elif 300 <= code < 400:
                status = "Maybe"
                confidence = 50
            else:
                status = "Maybe"
                confidence = 35
    except HTTPError as exc:
        code = int(exc.code)
        final_url = getattr(exc, "url", url) or url
        if code == 404:
            status = "Not Found"
            confidence = 90
        elif code in {401, 403, 429}:
            status = "Maybe"
            confidence = 40
        else:
            status = "Error"
            confidence = 0
    except (URLError, TimeoutError, OSError):
        code = 0
        final_url = url
        status = "Error"
        confidence = 0

    return {
        "site": site,
        "status": status,
        "confidence": confidence,
        "code": code,
        "url": final_url,
        "response_time": round(time.monotonic() - started, 3),
    }


@app.get("/")
def index():
    return PAGE, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "aliens-eye-web", "mode": "hosted-direct-scan"})


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

    selected = HOSTED_SITE_PRESETS[profile]
    started = time.monotonic()
    results = []
    with ThreadPoolExecutor(max_workers=min(12, len(selected))) as pool:
        futures = {pool.submit(check_site, site, username): site for site in selected}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception:
                site = futures[future]
                results.append({
                    "site": site,
                    "status": "Error",
                    "confidence": 0,
                    "code": 0,
                    "url": SITE_URLS[site].format(username),
                    "response_time": None,
                })

    results.sort(key=lambda row: (row["status"] != "Found", -row["confidence"], row["site"]))
    return jsonify({
        "username": username,
        "profile": profile,
        "hosted_mode": True,
        "sites_requested": len(selected),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "results": results,
    })
