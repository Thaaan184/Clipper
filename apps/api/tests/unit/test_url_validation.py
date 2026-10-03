"""Unit tests for URL validation and canonicalization."""

import pytest

from clipforge.core.errors import ValidationError
from clipforge.ingest.url import validate_and_canonicalize_url


def test_valid_youtube_urls():
    urls = [
        (
            "https://www.youtube.com/watch?v=cLhVLsius9w",
            ("https://www.youtube.com/watch?v=cLhVLsius9w", "cLhVLsius9w"),
        ),
        (
            "https://youtube.com/watch?v=cLhVLsius9w&t=100s",
            ("https://www.youtube.com/watch?v=cLhVLsius9w", "cLhVLsius9w"),
        ),
        (
            "https://youtu.be/cLhVLsius9w",
            ("https://www.youtube.com/watch?v=cLhVLsius9w", "cLhVLsius9w"),
        ),
        (
            "https://youtube.com/live/cLhVLsius9w?feature=share",
            ("https://www.youtube.com/watch?v=cLhVLsius9w", "cLhVLsius9w"),
        ),
        (
            "https://m.youtube.com/watch?v=RRJ2XZOkUOU",
            ("https://www.youtube.com/watch?v=RRJ2XZOkUOU", "RRJ2XZOkUOU"),
        ),
        (
            "https://www.youtube.com/shorts/3DvqXuKxDHk",
            ("https://www.youtube.com/watch?v=3DvqXuKxDHk", "3DvqXuKxDHk"),
        ),
    ]
    for raw, expected in urls:
        canonical, vid_id = validate_and_canonicalize_url(raw)
        assert (canonical, vid_id) == expected


def test_reject_invalid_scheme():
    with pytest.raises(ValidationError, match="scheme must be https"):
        validate_and_canonicalize_url("http://www.youtube.com/watch?v=cLhVLsius9w")


def test_reject_credentials():
    with pytest.raises(ValidationError, match="credentials"):
        validate_and_canonicalize_url("https://user:pass@www.youtube.com/watch?v=cLhVLsius9w")


def test_reject_disallowed_hosts():
    with pytest.raises(ValidationError, match="not in allowed hosts"):
        validate_and_canonicalize_url("https://vimeo.com/12345678")
    with pytest.raises(ValidationError, match="not in allowed hosts"):
        validate_and_canonicalize_url("https://evil.com/watch?v=cLhVLsius9w")


def test_reject_private_and_localhost_ips():
    with pytest.raises(ValidationError):
        validate_and_canonicalize_url("https://127.0.0.1/watch?v=cLhVLsius9w")
    with pytest.raises(ValidationError):
        validate_and_canonicalize_url("https://192.168.1.1/watch?v=cLhVLsius9w")
    with pytest.raises(ValidationError):
        validate_and_canonicalize_url("https://localhost/watch?v=cLhVLsius9w")


def test_reject_missing_video_id():
    with pytest.raises(ValidationError, match="Could not extract"):
        validate_and_canonicalize_url("https://www.youtube.com/watch?x=123")
