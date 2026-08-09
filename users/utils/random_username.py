import secrets
import string


def random_username(length: int = 20):
    suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(length))
    return f'user_{suffix}'
