#!/usr/bin/env python3
"""Removes old SPA files after the new build is live.

Usage: prune_spa.py <bucket> <dist dir>
A file is removed only when it is not in the current build and its last upload
is more than RETENTION_DAYS old.

RETENTION_DAYS is a team decision (2026-11-05), not a measured value. The clock
is the S3 upload time, not the time the file left the build. This is not a
promise to keep old assets for seven days after a deploy: a file uploaded long
ago goes in the first deploy that drops it, and a tab opened before that deploy
can then fail to load it. Only files uploaded in the last seven days survive.
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RETENTION_DAYS = 7


def stale_keys(objects, current, now, days=RETENTION_DAYS):
    limit = now - timedelta(days=days)
    return sorted(o["Key"] for o in objects if o["Key"] not in current
                  and datetime.fromisoformat(o["LastModified"].replace("Z", "+00:00")) < limit)


def aws(*args):
    return subprocess.run(["aws", *args], check=True, capture_output=True, text=True).stdout


def main(argv, run=aws, now=None):
    bucket, dist = argv[0], Path(argv[1])
    current = {str(p.relative_to(dist)) for p in dist.rglob("*") if p.is_file()}
    listing = run("s3api", "list-objects-v2", "--bucket", bucket, "--output", "json")
    objects = json.loads(listing or "{}").get("Contents") or []
    keys = stale_keys(objects, current, now or datetime.now(timezone.utc))
    for key in keys:
        run("s3", "rm", f"s3://{bucket}/{key}")
    print(f"removed {len(keys)} of {len(objects)} objects")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
