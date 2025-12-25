#!/usr/bin/env python3
"""Build list of KVN teams from humorbd.sql.

KVN teams are MODX resources with parent = 1031.
We output a json list with fields needed for incremental import.

Usage:
  python3 build_kvn_teams_list.py --sql /app/humorbd.sql --out /app/migration/kvn/kvn_teams_list.json
"""

import argparse
import json
import re
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Reuse robust SQL tuple parsing from people importer
from import_people_from_sql import _split_rows, _split_fields, _unescape_sql_string


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql", default="/app/humorbd.sql")
    parser.add_argument("--out", default="/app/migration/kvn/kvn_teams_list.json")
    parser.add_argument("--parent", type=int, default=1031)
    args = parser.parse_args()

    parent_id = str(args.parent)

    in_sc = False
    buf = []
    results = []

    with open(args.sql, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not in_sc:
                if line.startswith("INSERT INTO `modx_site_content`"):
                    in_sc = True
                    buf = [line]
                continue

            buf.append(line)
            if not line.strip().endswith(";"):
                continue

            blob = "".join(buf)
            in_sc = False
            buf = []

            m = re.search(r"VALUES\s*(.*);\s*$", blob, flags=re.DOTALL)
            if not m:
                continue

            rows = _split_rows(m.group(1))
            for r in rows:
                parts = _split_fields(r)
                if not parts or parts[0] is None:
                    continue

                # parent is at index 14 in this dump
                if len(parts) <= 14 or str(parts[14]).strip() != parent_id:
                    continue

                try:
                    rid = int(str(parts[0]).strip())
                except Exception:
                    continue

                def s(idx: int) -> str:
                    v = parts[idx] if idx < len(parts) else ""
                    return _unescape_sql_string(v) if isinstance(v, str) else ""

                results.append(
                    {
                        "id": rid,
                        "title": s(3),
                        "slug": s(6),
                        "status": "pending",
                    }
                )

            break

    results.sort(key=lambda x: x["id"])

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(results)} teams to {args.out}")


if __name__ == "__main__":
    main()
