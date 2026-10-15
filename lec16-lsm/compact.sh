#!/usr/bin/env bash
# Compact the whole database. RocksDB also flushes the memtable first if it
# holds any unflushed keys.
#
#   ./compact.sh ./my-db

set -euo pipefail

if [[ $# -ne 1 || -z "${1:-}" ]]; then
  echo "usage: $0 DB_PATH" >&2
  exit 1
fi

db=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")

if [[ ! -f "$db/CURRENT" ]]; then
  echo "no database at $db (run init_db.sh first)" >&2
  exit 1
fi

root=$(cd "$(dirname "$0")" && pwd)
if [[ -x "$root/.venv/bin/python3" ]]; then
  py="$root/.venv/bin/python3"
else
  py=python3
fi

DB_PATH="$db" "$py" - <<'PY'
import os
import sys

try:
    from rocksdict import Options, Rdict
except ImportError:
    sys.exit(
        "rocksdict is not installed.\n"
        "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    )

path = os.environ["DB_PATH"]
options = Options(raw_mode=True)
db = Rdict(path, options)
db.compact_range(None, None)
db.close()
print("compacted")
PY
