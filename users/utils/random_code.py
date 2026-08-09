import secrets
import string


def random_code(length: int = 6):
    return "".join(secrets.choice(string.digits) for _ in range(length))
