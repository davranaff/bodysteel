import hashlib
import hmac

from users.auth.configuration import password_reset_configuration, verification_configuration


def otp_digest(challenge_id, delivery_id, code):
    key = verification_configuration().code_hash_key
    value = f'{challenge_id}:{delivery_id}:{code}'.encode('utf-8')
    return hmac.new(key, value, hashlib.sha256).hexdigest()


def otp_matches(challenge, code):
    candidate = otp_digest(challenge.id, challenge.delivery_id, code)
    return hmac.compare_digest(challenge.code_digest, candidate)


def auth_challenge_digest(challenge_id, delivery_id, code):
    key = password_reset_configuration().code_hash_key
    value = f'{challenge_id}:{delivery_id}:{code}'.encode('utf-8')
    return hmac.new(key, value, hashlib.sha256).hexdigest()


def auth_challenge_matches(challenge, code):
    candidate = auth_challenge_digest(challenge.id, challenge.delivery_id, code)
    return hmac.compare_digest(challenge.code_digest, candidate)


def rate_limit_digest(scope, subject):
    key = verification_configuration().rate_hash_key
    value = f'{scope}:{subject}'.encode('utf-8')
    return hmac.new(key, value, hashlib.sha256).hexdigest()
