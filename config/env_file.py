"""Optional local ``.env`` loading for payment-provider credentials.

Only keys with an allowlisted prefix are read, and a value that is already in
the process environment (systemd ``EnvironmentFile``, CI, shell) always wins.
The file itself is gitignored; nothing here logs or echoes values.
"""
import os
import sys
from pathlib import Path


ALLOWED_PREFIXES = ('MULTICARD_',)


def load_env_file(path, environ=None):
    environ = os.environ if environ is None else environ
    if environ is os.environ and sys.argv[1:2] == ['test']:
        # Test runs must not depend on a developer's local credentials.
        return
    path = Path(path)
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        if key.startswith('export '):
            key = key[len('export '):].strip()
        if not key.startswith(ALLOWED_PREFIXES):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        environ.setdefault(key, value)
