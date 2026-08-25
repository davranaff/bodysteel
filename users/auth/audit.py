import logging


logger = logging.getLogger('bodysteel.auth')


def record(event, outcome, user_id=None, channel=None):
    """Emit bounded auth telemetry without identifiers, credentials, or challenge values."""
    logger.info(
        'auth_event=%s outcome=%s user_id=%s channel=%s',
        event,
        outcome,
        user_id if isinstance(user_id, int) else 'unknown',
        channel if channel in {'sms', 'email', 'telegram'} else 'unknown',
    )
