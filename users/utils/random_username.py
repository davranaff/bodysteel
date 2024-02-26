import random
import string


def random_username(length: int = 10):
    numbers_list = random.sample(string.digits, length)
    return "user_{}".format("".join(numbers_list))
