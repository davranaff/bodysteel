from rest_framework.views import exception_handler as drf_exception_handler


AUTH_VIEW_MODULES = ('users.auth.views', 'users.profile.views')


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    view = context.get('view')
    module = view.__class__.__module__ if view is not None else ''
    if response is None or not module.startswith(AUTH_VIEW_MODULES):
        return response

    status_code = response.status_code
    if status_code == 401:
        code, message = 'unauthorized', 'Authentication required'
    elif status_code == 403:
        code, message = 'forbidden', 'Forbidden'
    elif status_code == 429:
        code, message = 'rate_limited', 'Too many attempts'
    else:
        return response

    response.data = {'error': {'code': code, 'message': message}}
    response['Cache-Control'] = 'no-store'
    return response
