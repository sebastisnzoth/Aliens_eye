# Aliens Eye Web

A lightweight local web dashboard for the existing Aliens Eye username scanner.

## Run from source

```bash
git clone https://github.com/sebastisnzoth/Aliens_eye.git
cd Aliens_eye
git checkout aliens-eye-web
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
aliens_eye_web
```

Open:

```text
http://127.0.0.1:8080
```

To expose it on your local network:

```bash
aliens_eye_web --host 0.0.0.0 --port 8080
```

## What the first web version includes

- Username search form
- Quick / Full / Aggressive scan presets
- Reuses the existing Aliens Eye CLI scanner
- Results table with site, status, confidence, HTTP code and profile link
- Summary cards for checked / found / maybe / elapsed time
- `/health` endpoint
- `/api/scan` JSON endpoint
- Input validation and a 180-second scan timeout
- Responsive dark dashboard for desktop and mobile

## API

### Health

```bash
curl http://127.0.0.1:8080/health
```

### Scan

```bash
curl -X POST http://127.0.0.1:8080/api/scan \
  -H 'Content-Type: application/json' \
  -d '{"username":"octocat","profile":"quick"}'
```

## Notes

This first version deliberately runs the existing CLI in a subprocess instead of coupling the UI to internal scanner classes. That keeps the original terminal workflow stable while the web interface evolves.

Use Aliens Eye only for lawful OSINT research involving public information and in accordance with applicable laws and site terms.
