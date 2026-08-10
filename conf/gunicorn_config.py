import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

def _positive_integer(name, default, maximum):
    value = os.getenv(name, str(default))
    try:
        parsed = int(value)
    except ValueError:
        raise ValueError('{} must be an integer'.format(name)) from None
    if not 1 <= parsed <= maximum:
        raise ValueError('{} must be between 1 and {}'.format(name, maximum))
    return parsed


command = os.getenv('GUNICORN_COMMAND', str(BASE_DIR / 'venv' / 'bin' / 'gunicorn'))
pythonpath = os.getenv('GUNICORN_PYTHONPATH', str(BASE_DIR))
bind = os.getenv('GUNICORN_BIND', '127.0.0.1:8000')
workers = _positive_integer('GUNICORN_WORKERS', 3, maximum=32)
