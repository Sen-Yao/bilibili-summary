# Deployment

This project is Docker-first, but it intentionally avoids shipping a production scheduler. Keep scheduling close to your host environment so credentials and operational policy stay private.

## Build

```bash
docker build -t bilibili-summary:local .
```

## Configure

Create a private `.env` from `.env.example`:

```bash
cp .env.example .env
```

Fill in RSSHub, STT, LLM, Wallabag, and optional watch-later settings. Do not commit this file.

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

Keep the SQLite database and download directory on persistent storage. Back up the database if Wallabag entries are important.

## Operational Notes

- Start with `--dry-run` until all endpoints are configured.
- Use `show-jobs --status failed` to inspect failures.
- RSSHub Bilibili routes may fail when the cookie expires; see `docs/rsshub-cookie-automation.md`.
