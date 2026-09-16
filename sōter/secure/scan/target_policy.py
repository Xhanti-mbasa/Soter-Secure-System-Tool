import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit


class TargetRejected(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedTarget:
    url: str
    hostname: str
    port: int
    addresses: tuple[str, ...]


def _public_address(value: str) -> bool:
    ip = ipaddress.ip_address(value)
    return ip.is_global and not any(
        (ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_multicast, ip.is_reserved)
    )


def resolve_addresses(hostname: str, port: int) -> tuple[str, ...]:
    try:
        results = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise TargetRejected("Target hostname could not be resolved") from exc
    return tuple(sorted({item[4][0] for item in results}))


def validate_target(url: str, allow_private: bool = False) -> ValidatedTarget:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise TargetRejected("Target must be an absolute HTTP or HTTPS URL")
    if parsed.username or parsed.password:
        raise TargetRejected("Credentials are not permitted in target URLs")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise TargetRejected("Private or internal targets are not permitted")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = (str(ipaddress.ip_address(hostname)),)
    except ValueError:
        addresses = resolve_addresses(hostname, port)
    if not allow_private and (not addresses or any(not _public_address(ip) for ip in addresses)):
        raise TargetRejected("Private, reserved, or internal targets are not permitted")
    normalized = parsed._replace(netloc=f"{hostname}:{port}" if parsed.port else hostname, fragment="")
    return ValidatedTarget(normalized.geturl(), hostname, port, addresses)


def validate_redirect(origin: ValidatedTarget, location: str, allow_private: bool = False) -> str:
    candidate = validate_target(urljoin(origin.url, location), allow_private)
    if candidate.hostname != origin.hostname and not candidate.hostname.endswith(f".{origin.hostname}"):
        raise TargetRejected("Redirect escaped the authorized hostname scope")
    return candidate.url
