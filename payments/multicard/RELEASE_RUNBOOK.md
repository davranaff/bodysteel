# Выпуск онлайн-оплаты Multicard на прод

Порядок: backend → включение Multicard → сайт → отправка приложений на проверку.
Сайт можно выпустить за один день. Проверка в Google Play и App Store занимает от
нескольких часов до нескольких дней, поэтому день выхода приложений не гарантирован.

Ветки и версии:

| Часть | PR | Цель PR |
| --- | --- | --- |
| backend | https://github.com/davranaff/bodysteel/pull/1 | `main` |
| сайт | https://github.com/shakhbozv/bodysteel/pull/3 | `main` |
| приложение 1.2.0 (5) | https://github.com/davranaff/bodysteel_mobile/pull/2 | `feat/checkout-map-location` |

Приложение собирается только из `feat/multicard-release`. Старый PR
https://github.com/davranaff/bodysteel_mobile/pull/1 и `main` не содержат релиза 1.1.0,
сборка из них откатит прод.

## 1. Что подготовить заранее

**Для Android**
- upload-ключ `bodysteel-upload.jks` и пароли. SHA-256 ключа должен совпасть с
  `61:BE:5A:3F:E9:A0:B0:82:0B:6D:44:D1:4C:92:50:EA:81:33:33:05:42:31:67:B2:9D:86:A3:C9:BD:2A:B4:77`.
  Проверка: `keytool -list -v -keystore bodysteel-upload.jks`.
  Если ключ потерян, остаётся сброс upload key в Play Console, Google делает его не сразу.
- `android/app/google-services.json`. Без него сборка пройдёт, но push работать не будет.
- JDK 17 и Android SDK на машине сборки. На этом Mac их сейчас нет.

**Для iOS**
- `ios/BodySteelMobile/GoogleService-Info.plist`. Без него push работать не будет.

**В Play Console**
- App integrity → App signing key certificate → SHA-256 должен быть
  `A6:60:8D:2C:DD:FA:52:53:FC:58:E2:CB:11:88:17:1C:D9:9C:4E:E2:BA:47:2A:E4:03:01:C3:B7:AC:9F:A0:35`.
  Этот отпечаток прод уже отдаёт в `assetlinks.json`, теперь он есть и в репозитории.

**Для сервера**
- доступ к `/etc/bodysteel/gunicorn-release.env`;
- резервная копия базы перед миграцией.

**Тексты**
- `web/src/app/features/legal/termsContent.js`: в условиях есть оплата, согласованная
  с менеджером. Решите, менять ли этот текст.
- админка → «Оплата и доставка»: уберите наличные, если они там указаны.

## 2. Прод-значения

Значения собираются в `/Users/sukhrob/Desktop/bodysteel/multicard-prod.env`. Этот файл вне
репозиториев. На сервере те же строки добавляются в `/etc/bodysteel/gunicorn-release.env`.
Секрет не отправляйте в чаты и не коммитьте.

| Ключ | Значение | Откуда |
| --- | --- | --- |
| `MULTICARD_ENABLED` | `0`, на шаге 4 — `1` | |
| `MULTICARD_BASE_URL` | `https://mesh.multicard.uz` | документация Multicard |
| `MULTICARD_APPLICATION_ID` | | Multicard |
| `MULTICARD_SECRET` | | Multicard |
| `MULTICARD_STORE_ID` | | Multicard |
| `MULTICARD_CALLBACK_URL` | `https://api.bodysteel.uz/api/v1/payments/multicard/callback/` | слэш в конце обязателен |
| `MULTICARD_WEB_RETURN_URL` | `https://bodysteel.uz/payment/multicard` | |
| `MULTICARD_APP_RETURN_URL` | `https://bodysteel.uz/app/payment` | |
| `MULTICARD_DEFAULT_IKPU` | 17 цифр | tasnif.soliq.uz, бухгалтер |
| `MULTICARD_DEFAULT_PACKAGE_CODE` | | tasnif.soliq.uz |
| `MULTICARD_DELIVERY_IKPU` | 17 цифр | без него заказ с платной доставкой не оплатить |
| `MULTICARD_DELIVERY_PACKAGE_CODE` | | tasnif.soliq.uz |
| `MULTICARD_VAT_PERCENT`, `MULTICARD_TIN` | по решению бухгалтера | необязательно |
| `MULTICARD_CALLBACK_ALLOWED_IPS` | пусто | заполнять `195.158.26.90` только вместе с `AUTH_TRUSTED_PROXY_NETWORKS` |

Коды из примеров документации на прод не подходят. Если у товара свои коды, они задаются
в админке (`ИКПУ`, `Код упаковки`) и важнее значений по умолчанию.

В кабинете Multicard: если есть отдельный адрес для статусов, укажите
`https://api.bodysteel.uz/api/v1/payments/multicard/webhook/`. Это необязательно.

## 3. Backend с выключенным Multicard

1. Сделайте резервную копию базы.
2. Смёрджите backend-PR и выкатите его обычным способом.
3. Обновите зависимости (`pip install -r requirements.txt`) и выполните
   `python manage.py migrate` (добавляется `store.0050_product_fiscal_codes`).
4. Добавьте значения в env-файл, оставьте `MULTICARD_ENABLED=0`, перезапустите gunicorn.
5. Проверьте:

```bash
curl -s https://api.bodysteel.uz/api/v1/payments/methods/
```

Ожидается `{"data":{"multicard":false}}`. Покупатели ничего не замечают: заказы работают
как раньше.

## 4. Включение Multicard

1. Проверьте ключи, значения при этом не выводятся. Команда запускается с окружением
   из env-файла:

```bash
python manage.py shell -c "from payments.multicard.configuration import require_configuration; from payments.multicard.client import MulticardClient; print('token length', len(MulticardClient(require_configuration())._token()))"
```

2. Поставьте `MULTICARD_ENABLED=1` и перезапустите gunicorn.
3. Запрос из шага 3 должен вернуть `{"data":{"multicard":true}}`.

Пока сайт старый, он оформляет заказы без онлайн-оплаты. Менеджер видит их с пометкой
«💵 ОПЛАТА ПРИ ПОЛУЧЕНИИ». Сократите этот промежуток, сразу переходите к шагу 5.

## 5. Сайт

1. Смёрджите web-PR и выкатите его.
2. Проверьте файлы для ссылок:

```bash
curl -s https://bodysteel.uz/.well-known/apple-app-site-association | grep app/payment
```

```bash
curl -s https://bodysteel.uz/.well-known/assetlinks.json | grep -c "A6:60:8D"
```

Первая команда выводит `/app/payment/*`, вторая — `1`. Apple кэширует этот файл на своей
стороне, поэтому выкатывайте сайт до отправки приложения.

3. Купите товар на небольшую сумму настоящей картой и проверьте:
   - открылась страница Multicard на домене `multicard.uz`, `rhmt.uz` или `multicard.app`.
     Если сайт показывает ошибку оплаты, а счёт в логах создан, боевая страница на другом
     домене: его нужно добавить в `web/src/server/payment-inputs.js` и
     `src/features/checkout/model/paymentLinks.ts` в mobile;
   - после оплаты открылась страница «оплачено»;
   - в Telegram пришло «✅ ОПЛАЧЕН ОНЛАЙН»;
   - в админке у заказа статус оплаты «Оплачен»;
   - в чеке верные ИКПУ и код упаковки.
4. Верните тестовый платёж через кабинет Multicard, если нужно.

## 6. Приложения

Сборка **не** должна уйти на проверку раньше шага 5. Иначе проверяющий увидит
«Онлайн-оплата временно недоступна» вместо оформления заказа.

1. Работайте в папке `mobile-release`, там открыта ветка `feat/multicard-release`. Выполните `npm ci`, `npm run check`.
2. Положите конфигурацию Firebase из раздела 1.
3. iOS: `cd ios && pod install`, затем Xcode → Product → Archive → Distribute →
   App Store Connect. Подпись для App Store на этом Mac работает.
4. Android: `cd android && ./gradlew bundleRelease`. Загрузите
   `app/build/outputs/bundle/release/app-release.aab` и `mapping.txt`.
5. Проверьте версию: 1.2.0 (5) в обеих сборках.
6. Вставьте обновлённые заметки для проверяющих из `docs/release/STORE_RELEASE.md`, раздел 6.
7. Выпускайте постепенно: staged rollout в Play и phased release в App Store. Ошибку в
   приложении нельзя откатить быстро.
8. После публикации оплатите небольшой заказ из приложения на iPhone и Android и проверьте,
   что возврат с Multicard открывает приложение на экране оплаты.

## 7. Сборка 1.1.0 (4) после включения

Старое приложение не умеет запускать оплату и не отправляет `payment_method`.

- Заказ оформляется как раньше, ошибки покупатель не видит.
- Менеджер сразу получает заказ с пометкой «💵 ОПЛАТА ПРИ ПОЛУЧЕНИИ · старая версия
  приложения» и берёт оплату при получении.
- Заказ остаётся «Не оплачен». Это значит, что не все заказы будут предоплачены, пока
  покупатели не обновятся.
- Открытая до выката вкладка сайта ведёт себя так же.

Онлайн-заказ из новой версии менеджеру до оплаты не приходит. Он виден в админке со статусом
«Не оплачен». Купон, бонус и слот доставки списываются уже при создании заказа, поэтому у
брошенного заказа они останутся занятыми. Автоматической отмены таких заказов пока нет.

## 8. Откат

| Что случилось | Что сделать |
| --- | --- |
| Сбой оплаты, приложение ещё не вышло | Выкатите прошлую версию сайта, затем `MULTICARD_ENABLED=0` и перезапуск gunicorn. Заказы снова оформляются без онлайн-оплаты. |
| Сбой оплаты, новое приложение уже вышло | То же самое, но в новой версии заказ оформить нельзя, она покажет «Онлайн-оплата временно недоступна». Старая версия продолжит работать. |
| Ошибка в коде backend | Верните прошлый релиз. Перед этим `python manage.py migrate store 0049`, иначе старый код не сможет создавать товары. Коды товаров при этом удалятся. |
| Ошибка в приложении | Остановите staged rollout или phased release и выпустите новую сборку. |

`MULTICARD_ENABLED=0` не отменяет уже начатые платежи: callback и запрос статуса продолжают
работать. Не меняйте `MULTICARD_SECRET`, пока есть неоплаченные счета: их callback
перестанет проходить проверку подписи.

## 9. Что проверено

Проверено:
- backend: 390 тестов проходят (10 пропущены), новых миграций не требуется;
- сайт: lint, 244 теста, production-сборка;
- mobile: `npm run check`, 674 теста;
- iOS: archive 1.2.0 (5) и экспорт IPA с подписью для App Store, но без конфигурации Firebase.
  Эту сборку загружать нельзя, она удалена;
- iOS-симулятор, Release: приложение запускается, онбординг и главная работают с боевым API;
- Android: JS-бандл собирается;
- sandbox-оплата картой через сайт от 2026-11-05: заказ, счёт, callback, статус «оплачен».

Не проверено:
- оплата после последних изменений (`payment_method`, уведомления, перенос на релизную ветку).
  Эти изменения покрыты автотестами, повторный платёж не делался;
- оплата из приложения на устройстве;
- возврат по ссылке `/app/payment/...` в приложение: на симуляторе без подписи она открывается в Safari,
  поэтому маршрут покрыт только автотестами;
- подписанный Android AAB: нет ключа, JDK и SDK;
- боевой домен страницы Multicard и webhooks;
- что запущено на проде: сервер не проверялся, сверка сделана только по внешним ответам.
