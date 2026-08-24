import uuid
import warnings
from datetime import date
from pathlib import Path

from PIL import Image
from django.core.files.storage import default_storage
from django.http import HttpResponseNotAllowed, JsonResponse


MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_EXTENSIONS = {
    'GIF': '.gif',
    'JPEG': '.jpg',
    'PNG': '.png',
    'WEBP': '.webp',
}


def rich_html_image_upload(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    uploaded = request.FILES.get('image')
    if uploaded is None:
        return JsonResponse({'error': 'Выберите изображение.'}, status=400)
    if uploaded.size > MAX_IMAGE_BYTES:
        return JsonResponse({'error': 'Изображение должно быть не больше 10 МБ.'}, status=400)

    extension = _verified_extension(uploaded)
    if extension is None:
        return JsonResponse({'error': 'Поддерживаются JPG, PNG, WebP и GIF.'}, status=400)

    today = date.today()
    filename = '{}{}'.format(uuid.uuid4().hex, extension)
    relative_path = Path('rich-content', str(today.year), f'{today.month:02d}', filename)
    stored_path = default_storage.save(relative_path.as_posix(), uploaded)
    return JsonResponse({'url': default_storage.url(stored_path)})


def _verified_extension(uploaded):
    try:
        uploaded.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(uploaded) as image:
                image.verify()
                extension = IMAGE_EXTENSIONS.get(image.format)
        uploaded.seek(0)
        return extension
    except (
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        uploaded.seek(0)
        return None
