class IntegrationProblem(Exception):
    def __init__(self, status, title, detail, headers=None):
        super().__init__(detail)
        self.status = status
        self.title = title
        self.detail = detail
        self.headers = headers or {}


def invalid_request(detail='The Integration API request is invalid'):
    return IntegrationProblem(422, 'Invalid request', detail)
