def user_payload(user, token):
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'phone': user.phone,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'token': token.key,
    }
