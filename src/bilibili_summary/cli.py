from __future__ import annotations

import argparse

from .config import Settings
from .models import JobStatus
from .pipeline import Pipeline
from .store import JobStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bilibili-summary")
    parser.add_argument("--env-file", default=".env")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    poll = sub.add_parser("poll-once")
    poll.add_argument("--dry-run", action="store_true")
    run = sub.add_parser("run-pending")
    run.add_argument("--limit", type=int, default=5)
    run.add_argument("--dry-run", action="store_true")
    retry = sub.add_parser("retry-failed")
    retry.add_argument("--limit", type=int, default=5)
    retry.add_argument("--dry-run", action="store_true")
    show = sub.add_parser("show-jobs")
    show.add_argument("--status", choices=[s.value for s in JobStatus])
    show.add_argument("--limit", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env(args.env_file)
    store = JobStore(settings.db_path)
    if args.command == "init-db":
        store.init_db()
        print(f"initialized {settings.db_path}")
        return 0
    store.init_db()
    pipeline = Pipeline(settings, store)
    if args.command == "poll-once":
        count = pipeline.poll_once(dry_run=args.dry_run)
        print(f"rss videos {'seen' if args.dry_run else 'inserted'}: {count}")
        return 0
    if args.command == "run-pending":
        count = pipeline.run_pending(limit=args.limit, dry_run=args.dry_run)
        print(f"processed: {count}")
        return 0
    if args.command == "retry-failed":
        count = pipeline.retry_failed(limit=args.limit, dry_run=args.dry_run)
        print(f"retried: {count}")
        return 0
    if args.command == "show-jobs":
        statuses = [JobStatus(args.status)] if args.status else list(JobStatus)
        for row in store.list_by_status(*statuses, limit=args.limit):
            print(f"#{row['id']} {row['status']} {row['bvid']} {row['video_title'] or row['feed_title'] or ''} {row['error_message'] or ''}")
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
