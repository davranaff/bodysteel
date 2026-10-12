import os

PUSH_ENABLED = os.getenv('PUSH_ENABLED', '').lower() in {'1', 'true', 'yes'}
PUSH_FIREBASE_PROJECT_ID = os.getenv('PUSH_FIREBASE_PROJECT_ID', '')
PUSH_TOKEN_ENCRYPTION_KEYS = tuple(
    key.strip() for key in os.getenv('PUSH_TOKEN_ENCRYPTION_KEYS', '').split(',') if key.strip()
)
PUSH_MAX_CAMPAIGN_DEVICES = 20000
PUSH_MAX_DEVICES_PER_USER = 20
PUSH_DEVICE_STALE_DAYS = 90
