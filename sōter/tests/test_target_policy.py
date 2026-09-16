import socket

import pytest

from secure.scan.target_policy import TargetRejected, validate_redirect, validate_target


@pytest.mark.parametrize("url", ["http://127.0.0.1", "http://10.0.0.1", "http://192.168.1.10", "http://169.254.169.254", "http://[::1]", "http://localhost"])
def test_private_targets_rejected(url):
    with pytest.raises(TargetRejected):
        validate_target(url)


def test_shell_metacharacters_are_not_a_hostname():
    with pytest.raises(TargetRejected):
        validate_target("https://example.com;touch /tmp/pwned")


def test_public_target(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    result = validate_target("https://Example.COM/path#fragment")
    assert result.hostname == "example.com"
    assert result.url == "https://example.com/path"


def test_redirect_to_metadata_is_rejected(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    origin = validate_target("https://example.com")
    with pytest.raises(TargetRejected):
        validate_redirect(origin, "http://169.254.169.254/latest/meta-data")
