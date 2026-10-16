class OrderUnavailable(Exception):
    def __init__(self, message, code='out_of_stock'):
        super().__init__(message)
        self.code = code


class InvalidOrderIdempotencyKey(Exception):
    pass


class OrderIdempotencyConflict(Exception):
    pass
