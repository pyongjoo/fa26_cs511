#!/usr/bin/env bash
# Insert one key and flush the memtable to an L0 SST.
#
#   ./put.sh /tmp/lsm-demo a 1
#   ./put.sh /tmp/lsm-demo hello "world wide"

set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "usage: $0 DB_PATH KEY VALUE" >&2
  exit 1
fi

db=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
key=$2
shift 2
value="$*"

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

DB_PATH="$db" KEY="$key" VALUE="$value" "$py" - <<'PY'
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
db[os.environ["KEY"].encode()] = os.environ["VALUE"].encode()
db.flush(wait=True)
db.close()
PY

echo "flushed $key -> $value"
