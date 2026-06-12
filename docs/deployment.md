# Deployment

This project is Docker-first, but it intentionally avoids publishing a DockerHub image or shipping a production scheduler. Build the image on your host and keep scheduling close to the host environment so credentials and operational policy stay private.

## Build

```bash
git clone https://github.com/Sen-Yao/bilibili-summary.git
cd bilibili-summary
docker build -t bilibili-summary:local .
```

## Configure

Create a private `.env` from `.env.example`:

```bash
cp .env.example .env
```

Fill in RSSHub, STT, LLM, Wallabag, and optional watch-later settings. Do not commit this file.

If your STT service runs on the Docker host, set `STT_BASE_URL` to the host address reachable from bridge-network containers. For a standard Linux Docker bridge this is often:

```dotenv
STT_BASE_URL=http://172.17.0.1:8000/v1
STT_MODEL=deepdml/faster-whisper-large-v3-turbo-ct2
KEEP_AUDIO_FILES=false
LOG_LEVEL=INFO
```

## Run One Pass

```bash
docker run --rm \
  --env-file .env \
  -v "$PWD/data:/app/data" \
  bilibili-summary:local \
  run-resumable --limit 5
```

## Compose Example

`compose.example.yml` provides a minimal service definition. Build it with:

```bash
docker compose -f compose.example.yml build
```

Run polling and processing as separate host scheduler entries, for example:

```bash
docker compose -f compose.example.yml run --rm bilibili-summary-poll
docker compose -f compose.example.yml run --rm bilibili-summary run-resumable --limit 5
```

## Scheduling

Use cron, systemd timers, Unraid User Scripts, or another scheduler to run:

- `poll-once` every 30-60 minutes.
- `run-resumable --limit 5` every 30-60 minutes.
- `retry-failed --limit 3` less frequently, after checking error patterns.
- `cleanup-downloads` daily.

Keep the SQLite database and download directory on persistent storage. Back up the database if Wallabag entries are important.

## Operational Notes

- Start with `--dry-run` until all endpoints are configured.
- Use `show-jobs --status failed` to inspect failures.
- RSSHub Bilibili routes may fail when the cookie expires; see `docs/rsshub-cookie-automation.md`.
