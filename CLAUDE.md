# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Layout

The Django project lives under `companyapi/` — all `manage.py` commands must be run from there:

```bash
cd companyapi && python manage.py <command>
# or from repo root:
python companyapi/manage.py <command>
```

## Development Environment

Primary workflow is Docker Compose — runs Django + MySQL + Redis + Celery + Qdrant together:

```bash
docker-compose up          # start full stack
docker-compose up --build  # rebuild after dependency changes
```

Direct Python (no Docker) requires a local MySQL 8.0 instance and all env vars set manually.

## Required Environment Variables

Set in `companyapi/.env`:

```
DB_NAME=companyapi
DB_USER=root
DB_PASSWORD=<password>
DB_HOST=127.0.0.1
DB_PORT=3306
QDRANT_URL=http://localhost:6333
GEMINI_API_KEY=<key>   # required for AI audit; correction falls back to deterministic without it
GOOGLE_API_KEY=<key>   # alias accepted by langchain-google-genai
```

When `VERCEL=1` is set, the app switches to SQLite3 at `/tmp/db.sqlite3` and `DEBUG=False`.

## After Model Changes

Always run migrations before running tests or the server:

```bash
cd companyapi && python manage.py makemigrations && python manage.py migrate
```

## Celery Behavior

In bare-Python dev, `CELERY_TASK_ALWAYS_EAGER=True` — tasks execute **synchronously in-process** during the request. The AI audit and CSV correction complete before the HTTP response returns.

In Docker, a Redis broker (`redis://redis:6379/0`) is used; Celery workers run as a separate service and tasks are truly asynchronous.

## Validation Pipeline Architecture

`apps/validations/pipeline.py` runs a 7-agent deterministic pipeline on every uploaded ELD CSV:

1. **Parser** — Header, User List, CMV, Event segments
2. **Checksum Verifier** — Line and file data check values
3. **HOS Rules** — Hours of Service violations
4. **FMCSA Validation** — 7 sub-agents (header, users, CMV, events, login/logout, engine hours, odometer)
5. **Diagnostic Agent** — Data diagnostic events
6. **Malfunction Agent** — Escalated malfunction events
7. **Investigation Agent** — Root cause analysis

After the pipeline, `apps/ai_auditor/tasks.py` runs (async in Docker, eager in bare-Python):
- **Phase 1**: Gemini LLM audit (skipped gracefully on quota/key error)
- **Phase 2**: `AutonomousCorrectionAgent` — deterministic checksum fix + optional LLM patches → writes `uploads/<filename>_corrected.csv`

## ELD Validation Rules

These rules apply to all pipeline, agent, and correction code:

- **Only surface records that exist in the DB** — never fabricate or infer records not parsed from the file
- **Never inject `000000` synthetic time entries** — do not generate zero-time events in corrected output
- **Zero-value login/logout events are valid** — do not flag or correct them

Always validate all 10 segments: header, user list, CMV list, event list, malfunctions, diagnostics, login/logout, active/inactive status, event origin, unidentified drivers, checksums.

## Branch & PR Conventions

- Branch naming: `feature/<description>` or `fix/<description>`
- All changes via PR to `main` — no direct pushes to main

## Key Files

| File | Purpose |
|------|---------|
| `companyapi/companyapi/settings.py` | Django + Celery + DB + LLM config |
| `companyapi/apps/validations/pipeline.py` | 7-agent deterministic validation |
| `companyapi/apps/validations/autonomous_correction_agent.py` | Corrected CSV generation |
| `companyapi/apps/ai_auditor/tasks.py` | Celery async AI audit + correction dispatch |
| `vercel.json` | Vercel deployment (SQLite, wsgi.py entry) |
| `docker-compose.yml` | Full local dev stack |
