class OrderUnavailable(Exception):
    pass


class InvalidOrderIdempotencyKey(Exception):
    pass


class OrderIdempotencyConflict(Exception):
    pass
