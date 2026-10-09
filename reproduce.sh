#!/usr/bin/env sh
# Convenience wrapper: finds a Python 3.10+ and runs reproduce.py.
# Same as `python reproduce.py [--from-source] [--cache DIR]` on any OS.
cd "$(dirname "$0")" || exit 2
ok='import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'
has_pytest='import pytest'
# Prefer an interpreter that can also run the tests; $PY overrides everything.
for want in "$has_pytest" ""; do
  for py in "${PY:-}" python3 python py /c/ProgramData/anaconda3/python.exe; do
    [ -n "$py" ] || continue
    command -v "$py" >/dev/null 2>&1 || continue
    "$py" -c "$ok" >/dev/null 2>&1 || continue
    [ -z "$want" ] || "$py" -c "$want" >/dev/null 2>&1 || continue
    exec "$py" reproduce.py "$@"
  done
done
echo "Python 3.10 or newer not found. Install it, then run: python reproduce.py" >&2
exit 2
