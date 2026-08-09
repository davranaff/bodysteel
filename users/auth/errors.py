class AuthProblem(Exception):
    def __init__(self, status, code, message, retry_after=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after


def configuration_problem():
    return AuthProblem(503, 'service_unavailable', 'Authentication service unavailable')
