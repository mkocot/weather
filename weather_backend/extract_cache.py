#!/usr/bin/env python3
"""Extract cache bytearray values from a gzipped journalctl log."""

import gzip
import re
import sys


def extract_cache_values(gz_path: str) -> list[bytearray]:
    """Extract all final cache bytearray values from a gzipped journalctl log.

    The cache grows byte-by-byte as serial data arrives. Each batch ends
    when a ``module-id`` line appears. Returns the completed bytearray
    for each batch.
    """
    cache_values: list[bytearray] = []
    current_cache: bytearray | None = None

    with gzip.open(gz_path, "rt") as f:
        for line in f:
            if "cache:  bytearray(b'" in line:
                match = re.search(r"bytearray\(b'(.*)'\)", line)
                if match:
                    escaped = match.group(1)
                    current_cache = bytearray(
                        escaped.encode("latin-1")
                        .decode("unicode_escape")
                        .encode("latin-1")
                    )
            elif "module-id" in line:
                if current_cache is not None:
                    cache_values.append(current_cache)
                    current_cache = None

    return cache_values


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "journalctl-s1.gz"
    cache_values = extract_cache_values(path)

    print(f"Total batches: {len(cache_values)}\n")

    for i, cv in enumerate(cache_values):
        print(f"  Hex:    {cv.hex()}")
