from rest_framework import serializers

from moderation.models import ContentReport


REQUIRED_FIELDS = frozenset({'kind', 'reason'})
KIND_FIELDS = {
    ContentReport.Kind.REVIEW: frozenset({'review_id'}),
    ContentReport.Kind.AI_ANSWER: frozenset({'excerpt', 'conversation_id'}),
}


class ContentReportInputSerializer(serializers.Serializer):
    """Strict body for ``POST /api/v1/users/content-reports/``.

    Unknown keys are rejected. ``review_id`` is required iff ``kind=review``;
    ``excerpt`` is required iff ``kind=ai_answer``; ``conversation_id`` only
    accompanies AI answers. ``null`` optional values are treated as absent.
    """

    kind = serializers.ChoiceField(choices=ContentReport.Kind.choices)
    reason = serializers.ChoiceField(choices=ContentReport.Reason.choices)
    comment = serializers.CharField(
        required=False, allow_blank=True, max_length=ContentReport.COMMENT_MAX_LENGTH,
    )
    review_id = serializers.IntegerField(required=False, min_value=1, max_value=2**63 - 1)
    excerpt = serializers.CharField(required=False, max_length=ContentReport.EXCERPT_MAX_LENGTH)
    conversation_id = serializers.UUIDField(required=False)

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError('Unexpected or missing fields')
        present = {key: value for key, value in data.items() if value is not None}
        if not REQUIRED_FIELDS <= set(present) or not set(data) <= set(self.fields):
            raise serializers.ValidationError('Unexpected or missing fields')
        kind = present.get('kind')
        allowed = REQUIRED_FIELDS | {'comment'} | KIND_FIELDS.get(kind, frozenset())
        if not set(present) <= allowed:
            raise serializers.ValidationError('Field not allowed for this kind')
        values = super().to_internal_value(present)
        if kind == ContentReport.Kind.REVIEW and 'review_id' not in values:
            raise serializers.ValidationError('review_id is required')
        if kind == ContentReport.Kind.AI_ANSWER and 'excerpt' not in values:
            raise serializers.ValidationError('excerpt is required')
        values['comment'] = values.get('comment', '').strip()
        return values
