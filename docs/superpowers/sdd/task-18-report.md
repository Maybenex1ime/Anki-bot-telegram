# Task 18 Report: Deploy lên Fly.io

## What was created
Three files, contents verbatim from the brief:

- `Dockerfile` — python:3.12-slim base, installs requirements.txt, copies `app/`, runs `python -m app.bot.main`.
- `fly.toml` — app `reminder-zh-bot`, region `sin`, `DATA_DIR=/data`, volume `reminder_data` mounted at `/data`, 256mb shared VM. No `[http_service]` (pure worker, no port → Fly won't auto-stop the machine).
- `docs/DEPLOY.md` — Vietnamese runbook: install flyctl, `fly launch --no-deploy`, create volume, set BOT_TOKEN/OWNER_ID secrets, deploy, `fly scale count 1`, view logs, verify with /start, plus update and backup-restore sections.

## Verification
- Full test suite (no Python change): `.venv\Scripts\python.exe -m pytest tests/ -q` → **30 passed in 2.68s**.
- Files match the brief exactly.
- Commit: `5e2490a feat: Fly.io deployment (Dockerfile, fly.toml, runbook)` (3 files changed, 39 insertions). Git warned about LF→CRLF on the working copy — cosmetic only, no impact.

## Step 4 (real deploy & smoke test) — DEFERRED to project owner
Requires a Fly.io account plus BOT_TOKEN and OWNER_ID secrets not available in this session, and deploying is an outward-facing action. No flyctl installed, no deploy attempted, per the binding decision. Owner should follow `docs/DEPLOY.md`.

## Post-review fix
Reviewer flagged an Important finding: `app/config.py` evaluates `ZoneInfo("Asia/Ho_Chi_Minh")` at import time, but `tzdata` was not declared in `requirements.txt`. On Linux `python:3.12-slim`, tzlocal's tzdata dep is Windows-conditional, so a base image lacking `/usr/share/zoneinfo` would crash-loop on start. Fix: added unconditional `tzdata` to `requirements.txt` (zoneinfo prefers the system tzdb and falls back to the package — harmless everywhere).

- Installed into venv, re-ran suite: **30 passed in 2.98s**.
- Commit: `ce3fcb5 fix: declare tzdata for Linux images (zoneinfo fallback)` (1 file, 1 insertion).
