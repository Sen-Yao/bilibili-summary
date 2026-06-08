# Bilibili Summary

RSS-only Bilibili video summary pipeline migrated out of n8n.

## Scope

- Poll Bilibili followings RSS.
- Deduplicate jobs in SQLite.
- Classify food/cooking videos and skip them via watch-later bridge.
- For non-food videos: download audio, STT, summarize with `glm-5`, archive to Wallabag.
- Local OpenClawVM development/debug first. Yggdrasil Docker deployment is intentionally not included yet.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
cp .env.example .env
bilibili-summary init-db
bilibili-summary poll-once --dry-run
bilibili-summary run-pending --dry-run
```

Real Wallabag/watch-later writes require removing `--dry-run` after explicit approval.
