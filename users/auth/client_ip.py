from ipaddress import ip_address

from users.auth.configuration import trusted_proxy_networks


def client_ip(request):
    remote = _parse_address(request.META.get('REMOTE_ADDR', ''))
    if remote is None:
        return 'unavailable'
    trusted = trusted_proxy_networks()
    if not _is_trusted(remote, trusted):
        return str(remote)

    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if not isinstance(forwarded, str) or len(forwarded) > 1024:
        return str(remote)
    chain = [_parse_address(value.strip()) for value in forwarded.split(',') if value.strip()]
    if not chain or len(chain) > 16 or any(value is None for value in chain):
        return str(remote)
    for candidate in reversed([*chain, remote]):
        if not _is_trusted(candidate, trusted):
            return str(candidate)
    return str(chain[0])


def _parse_address(value):
    try:
        return ip_address(value)
    except ValueError:
        return None


def _is_trusted(address, networks):
    return any(address in network for network in networks)
