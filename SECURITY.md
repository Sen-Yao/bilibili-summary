# Security Policy

`bilibili-summary` is designed to keep secrets outside the repository.

## Never Commit

- `.env` files with real endpoints or credentials.
- Bilibili cookies, including `SESSDATA`, `bili_jct`, `DedeUserID`, or RSSHub `BILIBILI_COOKIE_*` values.
- LLM, Wallabag, RSSHub, watch-later, or OpenAI-compatible API keys.
- SQLite databases, downloaded audio, generated logs, browser profiles, or cookie exports.

## Recommended Handling

- Commit only `.env.example`.
- Store runtime secrets in a private `.env`, secret manager, or deployment-specific env file.
- Mount persistent data as a private volume when running Docker.
- Run a secret scan before pushing public commits.

## Reporting

If you find a leaked secret in a public repository, rotate that credential first, then rewrite repository history if needed. Treat browser session cookies as account credentials.
