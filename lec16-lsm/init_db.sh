#!/usr/bin/env bash
# Create a new empty RocksDB database directory.
# An existing directory at the same path is replaced.
#
#   ./init_db.sh /tmp/lsm-demo

set -euo pipefail

if [[ $# -ne 1 || -z "${1:-}" ]]; then
  echo "usage: $0 DB_PATH" >&2
  exit 1
fi

db=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
case "$db" in
  /|.|..)
    echo "refusing to initialize $db" >&2
    exit 1
    ;;
esac

root=$(cd "$(dirname "$0")" && pwd)
if [[ -x "$root/.venv/bin/python3" ]]; then
  py="$root/.venv/bin/python3"
else
  py=python3
fi

rm -rf "$db"

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
options.create_if_missing(True)
db = Rdict(path, options)
db.flush(wait=True)
db.close()
PY

echo "created $db"
