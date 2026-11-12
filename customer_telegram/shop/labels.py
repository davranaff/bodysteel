"""Words baked into the customer widgets (``WIDGET``) and sent in their state (``TEXT``)."""

_ERRORS = {
    'ru': {
        'wait': 'Секунду…', 'err': 'Не получилось. Попробуйте ещё раз.',
        'RATE_LIMITED': 'Слишком часто. Подождите пару секунд.', 'TIMEOUT': 'Бот не ответил. Попробуйте ещё раз.',
        'BUSY': 'Подождите, предыдущее действие ещё выполняется.',
        'NOT_ALLOWED': 'Это действие доступно только в чате с ботом.',
        'FAILED': 'Не получилось. Проверьте связь и попробуйте ещё раз.',
    },
    'uz': {
        'wait': 'Bir soniya…', 'err': 'Bajarilmadi. Yana urinib ko‘ring.',
        'RATE_LIMITED': 'Juda tez. Bir necha soniya kuting.', 'TIMEOUT': 'Bot javob bermadi. Yana urinib ko‘ring.',
        'BUSY': 'Kuting, oldingi amal hali bajarilmoqda.',
        'NOT_ALLOWED': 'Bu amal faqat bot bilan chatda ishlaydi.',
        'FAILED': 'Bajarilmadi. Aloqani tekshirib, yana urinib ko‘ring.',
    },
}

WIDGET = {
    'ru': {
        **_ERRORS['ru'], 'sum': 'сум', 'cat': 'Каталог BODYSTEEL',
        'find': '🔎 Чтобы найти товар, просто напишите его название в чат.',
        'item': 'Товар', 'prev': 'Назад', 'next': 'Ещё', 'none': 'Здесь пока ничего нет.',
        'out': 'Нет в наличии', 'add': 'В корзину', 'site': 'Подробнее на сайте', 'cart': 'Корзина',
        'empty': 'Корзина пуста. Добавьте товары из каталога.', 'total': 'Итого', 'order': 'Заказ',
        'how': 'Как получить заказ?', 'free': 'бесплатно', 'min': 'Заказ от', 'pay': 'Оплатить картой',
        'edit': 'Изменить корзину', 'recheck': 'Я оплатил — проверить', 'retry': 'Попробовать снова',
        'orders': 'Мои заказы', 'check': 'Проверьте заказ', 'sub': 'Товары', 'fee': 'Доставка',
        's_c': 'Ждёт подтверждения', 's_p': 'Ждёт оплаты', 's_ok': '✓ Оплачен', 's_x': 'Оплата не прошла',
        's_cod': '✓ Принят · оплата при получении',
    },
    'uz': {
        **_ERRORS['uz'], 'sum': 'so‘m', 'cat': 'BODYSTEEL katalogi',
        'find': '🔎 Mahsulotni topish uchun uning nomini chatga yozing.',
        'item': 'Mahsulot', 'prev': 'Orqaga', 'next': 'Yana', 'none': 'Bu yerda hozircha hech narsa yo‘q.',
        'out': 'Mavjud emas', 'add': 'Savatga', 'site': 'Saytda batafsil', 'cart': 'Savat',
        'empty': 'Savat bo‘sh. Katalogdan mahsulot qo‘shing.', 'total': 'Jami', 'order': 'Buyurtma',
        'how': 'Buyurtmani qanday olasiz?', 'free': 'bepul', 'min': 'Buyurtma', 'pay': 'Karta bilan to‘lash',
        'edit': 'Savatni o‘zgartirish', 'recheck': 'To‘ladim — tekshirish', 'retry': 'Qayta urinish',
        'orders': 'Buyurtmalarim', 'check': 'Buyurtmani tekshiring', 'sub': 'Mahsulotlar', 'fee': 'Yetkazib berish',
        's_c': 'Tasdiqlash kutilmoqda', 's_p': 'To‘lov kutilmoqda', 's_ok': '✓ To‘langan', 's_x': 'To‘lov o‘tmadi',
        's_cod': '✓ Qabul qilindi · yetkazilganda to‘lov',
    },
}

TEXT = {
    'ru': {
        'added': 'Добавлено в корзину ✓', 'limit': 'Больше добавить нельзя: столько есть на складе.',
        'gone': 'Этого товара больше нет в продаже.', 'stale': 'Это меню устарело. Откройте каталог заново.',
        'cart_full': 'В корзине может быть не больше 20 товаров.', 'search': 'Поиск: «{}»',
        'storefront_caption': '🛍 Каталог BODYSTEEL. Не видите витрину? Обновите Telegram.',
        'ask_contact': 'Шаг 1 из 3. Нажмите кнопку «📱 Поделиться номером» под полем ввода.',
        'ask_address': 'Шаг 2 из 3. Отправьте геолокацию кнопкой внизу или напишите адрес сообщением.',
        'share_location': '📍 Отправить геолокацию', 'use_saved': '↩️ Как в прошлый раз',
        'own_contact': 'Отправьте, пожалуйста, свой номер кнопкой «📱 Поделиться номером».',
        'bad_phone': 'Нужен узбекский номер (+998). Отправьте другой номер или напишите менеджеру.',
        'bad_address': 'Адрес слишком короткий. Напишите улицу и дом или отправьте геолокацию.',
        'outside': 'Геолокация должна быть в Узбекистане.',
        'order_caption': '🧾 Заказ BODYSTEEL на {} сум', 'order_caption_paid': '✅ Заказ № {} оплачен',
        'checkout_failed': 'Не удалось оформить заказ: {}. Измените корзину и попробуйте снова.',
        'pay_unavailable': 'Онлайн-оплата сейчас недоступна. Попробуйте чуть позже.',
        'not_paid_yet': 'Оплата пока не поступила. Если вы оплатили, подождите минуту.',
        'paid': 'Оплата получена. Спасибо! Менеджер свяжется с вами.',
        'unavailable_out_of_stock': 'товара не хватает на складе',
        'unavailable_minimum_order': 'сумма меньше минимальной для доставки',
        'unavailable_method_not_allowed': 'этот способ получения недоступен для товаров в корзине',
        'unavailable_other': 'проверьте корзину',
    },
    'uz': {
        'added': 'Savatga qo‘shildi ✓', 'limit': 'Ko‘proq qo‘shib bo‘lmaydi: omborda shuncha bor.',
        'gone': 'Bu mahsulot endi sotuvda yo‘q.', 'stale': 'Bu menyu eskirgan. Katalogni qayta oching.',
        'cart_full': 'Savatda 20 tadan ko‘p mahsulot bo‘lishi mumkin emas.', 'search': 'Qidiruv: «{}»',
        'storefront_caption': '🛍 BODYSTEEL katalogi. Vitrina ko‘rinmayaptimi? Telegramni yangilang.',
        'ask_contact': '1-qadam (3 tadan). Pastdagi «📱 Telefon raqamini yuborish» tugmasini bosing.',
        'ask_address': '2-qadam (3 tadan). Pastdagi tugma bilan joylashuvni yuboring yoki manzilni yozing.',
        'share_location': '📍 Joylashuvni yuborish', 'use_saved': '↩️ O‘tgan safargidek',
        'own_contact': 'Iltimos, o‘z raqamingizni «📱 Telefon raqamini yuborish» tugmasi bilan yuboring.',
        'bad_phone': 'O‘zbekiston raqami (+998) kerak. Boshqa raqam yuboring yoki menejerga yozing.',
        'bad_address': 'Manzil juda qisqa. Ko‘cha va uyni yozing yoki joylashuvni yuboring.',
        'outside': 'Joylashuv O‘zbekistonda bo‘lishi kerak.',
        'order_caption': '🧾 BODYSTEEL buyurtmasi: {} so‘m', 'order_caption_paid': '✅ № {} buyurtma to‘landi',
        'checkout_failed': 'Buyurtma berilmadi: {}. Savatni o‘zgartirib, qayta urinib ko‘ring.',
        'pay_unavailable': 'Onlayn to‘lov hozir ishlamayapti. Birozdan keyin urinib ko‘ring.',
        'not_paid_yet': 'To‘lov hali kelmadi. To‘lagan bo‘lsangiz, bir daqiqa kuting.',
        'paid': 'To‘lov qabul qilindi. Rahmat! Menejer siz bilan bog‘lanadi.',
        'unavailable_out_of_stock': 'omborda mahsulot yetarli emas',
        'unavailable_minimum_order': 'summa yetkazib berish uchun minimaldan kam',
        'unavailable_method_not_allowed': 'bu usul savatdagi mahsulotlar uchun mavjud emas',
        'unavailable_other': 'savatni tekshiring',
    },
}


def text(language, key):
    return TEXT['uz' if language == 'uz' else 'ru'][key]


def widget_labels(language):
    return WIDGET['uz' if language == 'uz' else 'ru']
