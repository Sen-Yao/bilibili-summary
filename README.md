# bilibili-summary

Turn a Bilibili following feed into searchable, long-form reading notes.

`bilibili-summary` is a small Python pipeline for people who follow many Bilibili creators but prefer reading the useful parts later. It polls an RSSHub feed, deduplicates videos in SQLite, filters cooking/food videos into a watch-later bridge, transcribes the remaining videos, asks an OpenAI-compatible LLM to write a polished Chinese article, and archives the result to Wallabag.

The project was extracted from a private n8n workflow and cleaned up for code-first, Docker-friendly operation.

## What It Does

- Polls a Bilibili following RSS feed from RSSHub.
- Stores resumable jobs in SQLite.
- Classifies food/cooking videos and optionally sends them to a watch-later bridge.
- Downloads audio for non-food videos.
- Sends audio to an OpenAI-compatible STT endpoint.
- Summarizes transcripts with an OpenAI-compatible chat completion endpoint.
- Publishes rich HTML entries to Wallabag.

```mermaid
flowchart LR
    RSS[RSSHub Bilibili feed] --> DB[(SQLite jobs)]
    DB --> Classify[LLM food classifier]
    Classify -->|food or cooking| Later[Watch-later bridge]
    Classify -->|other videos| Audio[Download audio]
    Audio --> STT[Speech-to-text API]
    STT --> Summary[LLM article writer]
    Summary --> Wallabag[Wallabag archive]
```

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
cp .env.example .env

bilibili-summary init-db
bilibili-summary poll-once --dry-run
bilibili-summary run-resumable --limit 1 --dry-run
```

The dry-run commands are intentionally safe: they initialize local state and exercise the pipeline without creating Wallabag entries or changing watch-later state. Remove `--dry-run` only after your private `.env` is configured.

## Configuration

Copy `.env.example` to `.env` and fill in your private endpoints and credentials.

| Variable | Purpose |
| --- | --- |
Required:

| Variable | Purpose |
| --- | --- |
| `RSS_FEED_URL` | RSSHub route for Bilibili following videos. |
| `STT_BASE_URL` | OpenAI-compatible transcription endpoint. |
| `LLM_BASE_URL` / `LLM_API_KEY` | OpenAI-compatible chat endpoint and API key. |
| `WALLABAG_BASE_URL` | Wallabag target instance. |
| `WALLABAG_CLIENT_ID` / `WALLABAG_CLIENT_SECRET` | Wallabag OAuth client credentials. |
| `WALLABAG_USERNAME` / `WALLABAG_PASSWORD` | Wallabag user credentials. |

Optional:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DB_PATH` | `data/bilibili_summary.sqlite3` | SQLite database path. |
| `DOWNLOAD_DIR` | `data/downloads` | Audio download directory. |
| `KEEP_AUDIO_FILES` | `false` | Keep `.m4a` files after STT instead of deleting them. |
| `LOG_LEVEL` | `INFO` | Docker-friendly log level: `DEBUG`, `INFO`, or `ERROR`. |
| `STT_MODEL` | `deepdml/faster-whisper-large-v3-turbo-ct2` | Speech-to-text model. |
| `LLM_MODEL` | `glm-5` | Chat model used for classification and article writing. |
| `WATCH_LATER_URL` / `WATCH_LATER_TOKEN` | unset | Optional bridge for food/cooking videos. |

`WATCH_LATER_URL` is optional. When a video is classified as food/cooking, the pipeline skips summarization and calls `GET {WATCH_LATER_URL}?bvid=<BVID>`. If `WATCH_LATER_TOKEN` is set, it is sent as `X-Api-Token`. When the URL is unset, the job is still marked `skipped`, but no external watch-later action is taken.

Downloads are written as `.part` files first and atomically renamed to `.m4a` after a successful download. By default, audio files are deleted after STT succeeds. Set `KEEP_AUDIO_FILES=true` only when you intentionally want to retain audio.

Never commit `.env`, cookies, downloaded audio, SQLite databases, or generated logs. The repository ignore rules and Docker examples are designed around that assumption.

## CLI

```bash
bilibili-summary init-db
bilibili-summary poll-once [--dry-run]
bilibili-summary run-pending [--limit 5] [--dry-run]
bilibili-summary run-resumable [--limit 5] [--dry-run]
bilibili-summary retry-failed [--limit 5] [--dry-run]
bilibili-summary show-jobs [--status discovered|failed|archived] [--limit 20]
bilibili-summary cleanup-downloads [--dry-run]
```

Use `run-resumable` for routine operation. It continues jobs from discovered, audio-downloaded, transcribed, and summarized states.
Use `cleanup-downloads --dry-run` to inspect removable `.part` files and audio files that are no longer needed.

## Docker

Build locally:

```bash
docker build -t bilibili-summary:local .
```

Run with a private env file and a persistent data volume:

```bash
docker run --rm \
  --env-file .env \
  -v "$PWD/data:/app/data" \
  bilibili-summary:local \
  run-resumable --limit 5
```

For a scheduler-friendly example, see `compose.example.yml` and `docs/deployment.md`. If your STT service runs on the Docker host, configure `STT_BASE_URL` with the host address reachable from containers.

## RSSHub Cookie Automation

Bilibili routes in RSSHub often require a fresh logged-in cookie. This repository includes a documented browser-profile based approach in `docs/rsshub-cookie-automation.md`: keep a persistent Chromium profile logged in to Bilibili, export cookies on a schedule, update a private RSSHub env file, restart RSSHub, and health-check the feed before accepting the new cookie.

The automation is intentionally documented as a deployment pattern rather than hard-coding any private host, cookie, or container name into this public repository.

## Development

```bash
pip install -e '.[test]'
pytest
```

The test suite covers RSS parsing, retry behavior, SQLite job state, Wallabag dry-run behavior, and LLM JSON extraction.

## Logs

The CLI writes structured text logs to stdout, so Docker and Unraid can collect them with `docker logs`. Set `LOG_LEVEL=DEBUG` for verbose diagnostics or `LOG_LEVEL=ERROR` for quieter scheduled runs. Logs include job ids, BVIDs, status transitions, cleanup counts, and exception traces; they do not print API keys, cookies, or `.env` contents.

## Security

This project is safe to publish only when real credentials remain outside the repository. See `SECURITY.md` for the handling policy. In short: keep `.env`, browser profiles, cookies, SQLite data, audio files, and logs private.
