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


## Agent API service

The API service is optional and should run as a long-lived Docker container when agents need to submit specific Bilibili videos. Add `API_TOKEN` to the private env file and keep it out of Git.

```bash
docker run -d \
  --name bilibili-summary-api \
  --restart unless-stopped \
  --env-file /path/to/private.env \
  -p 18766:8000 \
  -v /path/to/data:/app/data \
  --entrypoint bilibili-summary-api \
  bilibili-summary:local
```

For LAN use, publish the port you intend agents to reach. For public use through Cloudflare Tunnel or another proxy, point the public hostname at the LAN address and keep `Authorization: Bearer <API_TOKEN>` required for all processing calls.

```bash
curl http://127.0.0.1:18766/health
curl -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"video":"BV1xx411c7mD","run_now":false}' \
  http://127.0.0.1:18766/api/videos/process
```

The API writes request and job logs to stdout, so `docker logs bilibili-summary-api` should show health, enqueue, processing, and exception events without exposing secrets.
