"""URL validation and canonicalization for ingest."""

import ipaddress
import re
from urllib.parse import parse_qs, urlparse

from clipforge.core.errors import ValidationError

DEFAULT_ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}

YOUTUBE_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{11}$")


def validate_and_canonicalize_url(
    url: str,
    allowed_hosts: set[str] | None = None,
    max_length: int = 2048,
) -> tuple[str, str]:
    """
    Validate input URL against security rules and return (canonical_url, video_id).

    Raises:
        ValidationError: if URL fails any security check or video_id cannot be found.
    """
    if not url or len(url) > max_length:
        raise ValidationError(f"URL length must be between 1 and {max_length} characters")

    parsed = urlparse(url)

    if parsed.scheme.lower() != "https":
        raise ValidationError(f"URL scheme must be https, got '{parsed.scheme}'")

    if parsed.username or parsed.password:
        raise ValidationError("URL must not contain embedded user/password credentials")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValidationError("URL is missing a valid hostname")

    # Reject private/localhost IP addresses
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            raise ValidationError(f"Host '{hostname}' is a private/loopback IP and is prohibited")
    except ValueError:
        # Not a raw IP literal, which is fine
        pass

    if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        raise ValidationError(f"Host '{hostname}' is not permitted")

    hosts = allowed_hosts if allowed_hosts is not None else DEFAULT_ALLOWED_HOSTS
    if hostname not in hosts:
        raise ValidationError(f"Host '{hostname}' is not in allowed hosts: {sorted(hosts)}")

    video_id: str | None = None

    if hostname == "youtu.be":
        # Path is /{video_id}
        path_clean = parsed.path.strip("/")
        if path_clean:
            candidate = path_clean.split("/")[0]
            if YOUTUBE_ID_REGEX.match(candidate):
                video_id = candidate
    elif hostname in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        path = parsed.path
        if path.startswith("/watch"):
            query_params = parse_qs(parsed.query)
            if "v" in query_params and query_params["v"]:
                candidate = query_params["v"][0]
                if YOUTUBE_ID_REGEX.match(candidate):
                    video_id = candidate
        elif path.startswith("/live/"):
            candidate = path.split("/live/")[1].split("/")[0].split("?")[0]
            if YOUTUBE_ID_REGEX.match(candidate):
                video_id = candidate
        elif path.startswith("/shorts/"):
            candidate = path.split("/shorts/")[1].split("/")[0].split("?")[0]
            if YOUTUBE_ID_REGEX.match(candidate):
                video_id = candidate

    if not video_id:
        raise ValidationError(
            f"Could not extract a valid 11-character YouTube video ID from URL '{url}'"
        )

    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    return canonical_url, video_id
