from customer_telegram.configuration import require_configuration
from customer_telegram.i18n import message


def language_keyboard():
    return {'inline_keyboard': [[
        {'text': 'Русский', 'callback_data': 'lang:ru'},
        {'text': "O‘zbekcha", 'callback_data': 'lang:uz'},
    ]]}


def main_menu(language):
    return {'keyboard': [
        [{'text': message(language, 'menu_orders')}, {'text': message(language, 'menu_notifications')}],
        [{'text': message(language, 'menu_language')}, {'text': message(language, 'menu_store')}],
        [{'text': message(language, 'menu_help')}, {'text': message(language, 'menu_unlink')}],
    ], 'resize_keyboard': True}


def contact_keyboard(language):
    return {'keyboard': [[{
        'text': message(language, 'share_phone'),
        'request_contact': True,
    }]], 'resize_keyboard': True, 'one_time_keyboard': True}


def remove_keyboard():
    return {'remove_keyboard': True}


def notification_keyboard(language):
    return {'inline_keyboard': [[
        {'text': message(language, 'notifications_yes'), 'callback_data': 'notify:on'},
        {'text': message(language, 'notifications_no'), 'callback_data': 'notify:off'},
    ]]}


def unlink_keyboard(language):
    return {'inline_keyboard': [[
        {'text': message(language, 'unlink_yes'), 'callback_data': 'unlink:yes'},
        {'text': message(language, 'unlink_no'), 'callback_data': 'unlink:no'},
    ]]}


def orders_keyboard(language, page, has_previous, has_next, orders):
    rows = [[{
        'text': '{} #{}'.format(message(language, 'details'), order_code),
        'callback_data': 'order:{}'.format(order_id),
    }] for order_id, order_code in orders]
    navigation = []
    if has_previous:
        navigation.append({'text': message(language, 'previous'), 'callback_data': 'orders:{}'.format(page - 1)})
    if has_next:
        navigation.append({'text': message(language, 'next'), 'callback_data': 'orders:{}'.format(page + 1)})
    if navigation:
        rows.append(navigation)
    return {'inline_keyboard': rows}


def store_keyboard(language):
    return {'inline_keyboard': [[{
        'text': message(language, 'open_store'),
        'url': require_configuration().store_origin,
    }]]}
