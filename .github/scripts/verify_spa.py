#!/usr/bin/env python3
"""Checks that the site serves this build before old assets are removed.

Usage: verify_spa.py <site url> <dist dir>
The served index.html must equal dist/index.html, and every /assets/ file it
references must return the same bytes as the file in dist.
"""

import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ATTEMPTS = 5
WAIT_SECONDS = 10
ASSET = re.compile(r'(?:src|href)="(/assets/[^"]+)"')


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "dowon-deploy-check"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def problems(site_url, dist):
    site_url = site_url.rstrip("/")
    expected = (dist / "index.html").read_bytes()
    try:
        served = fetch(site_url + "/")
    except (urllib.error.URLError, OSError) as exc:
        return [f"index.html: {exc}"]
    if served != expected:
        return ["index.html: the site does not serve this build"]
    found = []
    assets = ASSET.findall(expected.decode("utf-8"))
    if not assets:
        found.append("index.html: no /assets/ reference found")
    for path in assets:
        try:
            if fetch(site_url + path) != (dist / path.lstrip("/")).read_bytes():
                found.append(f"{path}: content differs")
        except (urllib.error.URLError, OSError) as exc:
            found.append(f"{path}: {exc}")
    return found


def main(argv, sleep=time.sleep):
    site_url, dist = argv[0], Path(argv[1])
    found = []
    for attempt in range(ATTEMPTS):
        found = problems(site_url, dist)
        if not found:
            print("site serves this build")
            return 0
        if attempt < ATTEMPTS - 1:
            sleep(WAIT_SECONDS)
    for line in found:
        print(f"::error::{line}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
