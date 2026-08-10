import hashlib
import hmac

from django.conf import settings

from integration.errors import IntegrationProblem


SCOPES = frozenset({'products:read', 'inventory:read', 'carts:write'})


def authorize_request(request, required_scope):
    token = _bearer_token(request.headers.get('Authorization'))
    credentials = _credentials()
    if not credentials:
        raise IntegrationProblem(503, 'Service unavailable', 'Integration credentials are not configured')

    presented = _digest(token) if token else None
    matched_scopes = None
    for credential_digest, scopes in credentials:
        candidate = presented or bytes(len(credential_digest))
        if hmac.compare_digest(candidate, credential_digest) and presented is not None:
            matched_scopes = scopes

    if matched_scopes is None:
        raise IntegrationProblem(
            401,
            'Unauthorized',
            'A valid BodySteel integration credential is required',
            {'WWW-Authenticate': 'Bearer realm="bodysteel-integration"'},
        )
    if required_scope not in matched_scopes:
        raise IntegrationProblem(403, 'Forbidden', 'The credential does not grant the required scope')


def _credentials():
    configured = getattr(settings, 'SAVDOQ_INTEGRATION_CREDENTIALS', ())
    parsed = []
    seen = set()
    if not isinstance(configured, (tuple, list)) or len(configured) > 10:
        raise IntegrationProblem(503, 'Service unavailable', 'Integration credentials are misconfigured')
    for credential in configured:
        token = credential.get('token') if isinstance(credential, dict) else None
        scopes = credential.get('scopes') if isinstance(credential, dict) else None
        if not _valid_token(token) or not _valid_scopes(scopes):
            raise IntegrationProblem(503, 'Service unavailable', 'Integration credentials are misconfigured')
        digest = _digest(token)
        if digest in seen:
            raise IntegrationProblem(503, 'Service unavailable', 'Integration credentials are misconfigured')
        seen.add(digest)
        parsed.append((digest, frozenset(scopes)))
    return parsed


def _bearer_token(value):
    if not value or len(value) > 4_103:
        return None
    scheme, separator, token = value.partition(' ')
    if separator != ' ' or scheme.lower() != 'bearer' or not _valid_token(token):
        return None
    return token


def _valid_token(token):
    return is_valid_integration_token(token)


def is_valid_integration_token(token):
    return (
        isinstance(token, str)
        and 32 <= len(token) <= 4_096
        and not any(character.isspace() for character in token)
    )


def _valid_scopes(scopes):
    return (
        isinstance(scopes, (tuple, list))
        and bool(scopes)
        and len(scopes) == len(set(scopes))
        and set(scopes).issubset(SCOPES)
    )


def _digest(token):
    return hashlib.sha256(token.encode('utf-8')).digest()
