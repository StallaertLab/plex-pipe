"""Offline tests for the example-data registry.

Validate that the download URL and checksum shipped with the package are well
formed, without downloading the archive, so the test suite carries no network
dependency. The download itself is exercised by calling
``plex_pipe.fetch_example()``, where pooch validates the archive against the
recorded hash.
"""

import re

from plex_pipe.datasets import (
    EXAMPLE_DATA_ARCHIVE,
    EXAMPLE_DATA_BASE_URL,
    EXAMPLE_DATA_SHA256,
    EXAMPLE_DATA_TAG,
    _REGISTRY,
)


def test_sha256_is_well_formed():
    """The recorded checksum is a valid SHA256: 64 lowercase hex characters."""
    assert re.fullmatch(r"[0-9a-f]{64}", EXAMPLE_DATA_SHA256)


def test_base_url_points_at_the_data_release():
    """The download URL is built from the dedicated data-release tag."""
    assert EXAMPLE_DATA_BASE_URL.startswith(
        "https://github.com/StallaertLab/plex-pipe/releases/download/"
    )
    assert EXAMPLE_DATA_TAG in EXAMPLE_DATA_BASE_URL
    # Pooch concatenates base_url and filename, so the trailing slash is required.
    assert EXAMPLE_DATA_BASE_URL.endswith("/")


def test_archive_is_registered_with_its_hash():
    """The registry maps the archive name to the recorded checksum."""
    assert _REGISTRY.registry[EXAMPLE_DATA_ARCHIVE] == (
        f"sha256:{EXAMPLE_DATA_SHA256}"
    )


def test_resolved_asset_url_is_exact():
    """base_url joined with the archive name resolves to the release asset."""
    assert EXAMPLE_DATA_BASE_URL + EXAMPLE_DATA_ARCHIVE == (
        "https://github.com/StallaertLab/plex-pipe/releases/download/"
        "example-data-v1/plexpipe_example_data.zip"
    )
