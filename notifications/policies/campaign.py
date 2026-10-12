import json
import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError

from notifications.serializers.audience import AudienceSerializer


def validate_campaign(campaign):
    serializer = AudienceSerializer(data=campaign.audience)
    if not serializer.is_valid():
        raise ValidationError({'audience': 'Некорректные или неизвестные фильтры аудитории.'})
    if campaign.target_url:
        url = urlsplit(campaign.target_url)
        valid_path = re.fullmatch(r'/app(?:/(?:catalog|orders|favorites|chat)|/(?:product|category)/[A-Za-z0-9_-]{1,250})?/?', url.path)
        if (url.scheme != 'https' or url.netloc != 'bodysteel.uz' or url.username or url.password
                or url.query or url.fragment or not valid_path):
            raise ValidationError({'target_url': 'Используйте разрешённую HTTPS-страницу приложения BodySteel.'})
    for language in ('ru', 'uz'):
        title, body = getattr(campaign, 'title_' + language), getattr(campaign, 'body_' + language)
        if not title.strip() or not body.strip():
            raise ValidationError('Заполните заголовок и текст на обоих языках.')
        payload = json.dumps({'notification': {'title': title, 'body': body}, 'data': {
            'notification_id': '0' * 36, 'scope': '0' * 36, 'url': campaign.target_url,
        }}, ensure_ascii=False).encode()
        if len(payload) > 3400:
            raise ValidationError({'body_' + language: 'Сообщение слишком длинное для push. Сократите текст.'})
