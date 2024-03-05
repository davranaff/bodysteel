import random
import string


def random_code(length: int = 6):
    numbers_list = random.sample(string.digits, length)
    return "".join(numbers_list)
