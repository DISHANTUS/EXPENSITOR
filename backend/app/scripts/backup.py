"""Full-state backup / restore CLI — the disaster-recovery path.

Runs directly against the database with NO authentication, because after a wipe
there is no developer account left to authorize an API call. This is what you
reach for when "the data got lost".

Usage (inside the api container):
    python -m app.scripts.backup export                  # → backups/advary-<stamp>.json
    python -m app.scripts.backup export --path /tmp/x.json
    python -m app.scripts.backup restore --latest        # newest backup in the folder
    python -m app.scripts.backup restore --path backups/advary-2026-06-18-101500.json

Restore is idempotent: existing rows are skipped, missing ones are recreated
(primary keys + password hashes preserved), so everyone logs back in unchanged.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.core.database import AsyncSessionLocal
from app.services import backup_service


async def _export(path: str | None) -> None:
    async with AsyncSessionLocal() as session:
        target, counts = await backup_service.export_to_file(session, Path(path) if path else None)
    total = sum(counts.values())
    print(f"Backed up {total} rows across {len(counts)} tables → {target}")
    for name, n in sorted(counts.items()):
        print(f"  {name}: {n}")


async def _restore(path: str | None, latest: bool) -> None:
    target = Path(path) if path else (backup_service.latest_backup() if latest else None)
    if target is None:
        raise SystemExit("Provide --path <file> or --latest (no backups found).")
    if not target.is_file():
        raise SystemExit(f"Backup file not found: {target}")
    async with AsyncSessionLocal() as session:
        inserted = await backup_service.import_from_file(session, target)
    total = sum(inserted.values())
    print(f"Restored {total} rows from {target}")
    for name, n in sorted(inserted.items()):
        if n:
            print(f"  {name}: +{n}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Advary full-state backup / restore")
    sub = parser.add_subparsers(dest="command", required=True)

    p_export = sub.add_parser("export", help="Write a full-state snapshot to a JSON file")
    p_export.add_argument("--path", help="Output file (default: backups/advary-<timestamp>.json)")

    p_restore = sub.add_parser("restore", help="Recreate missing rows from a snapshot")
    p_restore.add_argument("--path", help="Snapshot file to restore from")
    p_restore.add_argument("--latest", action="store_true", help="Use the newest backup in the folder")

    args = parser.parse_args()
    if args.command == "export":
        asyncio.run(_export(args.path))
    elif args.command == "restore":
        asyncio.run(_restore(args.path, args.latest))


if __name__ == "__main__":
    main()
