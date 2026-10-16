from dataclasses import dataclass


@dataclass(frozen=True)
class MapLinks:
    google: str
    yandex: str


def order_map_links(order):
    """External map links for an order's delivery point, or ``None`` without one."""
    latitude = getattr(order, 'address_latitude', None)
    longitude = getattr(order, 'address_longitude', None)
    if latitude is None or longitude is None:
        return None
    lat = '{:.6f}'.format(float(latitude))
    lng = '{:.6f}'.format(float(longitude))
    return MapLinks(
        google=f'https://maps.google.com/?q={lat},{lng}',
        yandex=f'https://yandex.uz/maps/?pt={lng},{lat}&z=17&l=map',
    )
