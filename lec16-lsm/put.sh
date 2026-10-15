#!/usr/bin/env bash
# Insert one or more key-value pairs, then flush the memtable to an L0 SST.
# Quote a value that contains spaces. The argument count after DB_PATH must be even.
#
#   ./put.sh /tmp/lsm-demo a 1
#   ./put.sh /tmp/lsm-demo a 1 b 2 c 3
#   ./put.sh /tmp/lsm-demo hello "world wide" d 4

set -euo pipefail

if [[ $# -lt 3 || $(( ($# - 1) % 2 )) -ne 0 ]]; then
  echo "usage: $0 DB_PATH KEY VALUE [KEY VALUE ...]" >&2
  exit 1
fi

db=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
shift

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

"$py" - "$db" "$@" <<'PY'
import sys

try:
    from rocksdict import Options, Rdict
except ImportError:
    sys.exit(
        "rocksdict is not installed.\n"
        "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    )

path = sys.argv[1]
pairs = sys.argv[2:]
options = Options(raw_mode=True)
db = Rdict(path, options)
for index in range(0, len(pairs), 2):
    key = pairs[index]
    value = pairs[index + 1]
    db[key.encode()] = value.encode()
    print(f"inserted {key} -> {value}")
db.flush(wait=True)
db.close()
print("flushed")
PY
