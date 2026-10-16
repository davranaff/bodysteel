from django.utils.crypto import salted_hmac

from store.catalog.reviews.models import Review


ANONYMOUS_AUTHOR = 'Покупатель'
AUTHOR_KEY_SALT = 'bodysteel.review-author.v1'


def author_key(user_id):
    """Stable, opaque author identifier that lets clients hide an author's reviews.

    It is an HMAC of the account id, so it never reveals the id, phone or email
    and cannot be reversed or linked to other public identifiers.
    """
    if user_id is None:
        return None
    return salted_hmac(AUTHOR_KEY_SALT, str(user_id), algorithm='sha256').hexdigest()[:32]


def anonymize_user_reviews(user):
    """Detach and anonymize a deleted customer's reviews.

    The star rating stays so product aggregates remain truthful; the author name
    becomes a generic label and the free-text comment is removed.
    """
    return Review.objects.filter(user=user).update(
        user=None,
        full_name=ANONYMOUS_AUTHOR,
        comment='',
    )
