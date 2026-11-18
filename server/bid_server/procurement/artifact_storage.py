"""Private export storage. No client paths; publish references only after verification.

A finalized file without a committed reference is an orphan; keep it private for
reconciliation rather than deleting any possibly committed artifact.
"""
import hashlib
import os
from pathlib import Path
import tempfile
import re

from django.conf import settings
from bid_server.config import REPOSITORY_ROOT


MAX_ARTIFACT_BYTES = 10 * 1024 * 1024


class ArtifactStorageError(Exception):
    """Safe storage failure; do not expose paths or underlying errors."""


def _root():
    configured = getattr(settings, "PRIVATE_MEDIA_ROOT", None)
    if not configured:
        raise ArtifactStorageError("Private artifact storage unavailable.")
    root = Path(configured)
    if not root.is_absolute() or root.is_symlink():
        raise ArtifactStorageError("Private artifact storage unavailable.")
    try:
        root = root.resolve(strict=True)
        if not root.is_dir() or root.is_relative_to(REPOSITORY_ROOT):
            raise ArtifactStorageError("Private artifact storage unavailable.")
        return root
    except (OSError, ValueError):
        raise ArtifactStorageError("Private artifact storage unavailable.") from None


def _verify(path, digest, size):
    if not 0 < size <= MAX_ARTIFACT_BYTES or path.is_symlink():
        raise ArtifactStorageError("Artifact integrity check failed.")
    with path.open("rb") as stream:
        raw = stream.read(MAX_ARTIFACT_BYTES + 1)
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
        raise ArtifactStorageError("Artifact integrity check failed.")
    return raw


def store_verified_artifact(raw, digest, size):
    """Stage and verify, then atomically finalize a unique private storage key."""
    if len(raw) != size or not 0 < size <= MAX_ARTIFACT_BYTES or hashlib.sha256(raw).hexdigest() != digest:
        raise ArtifactStorageError("Artifact integrity check failed.")
    root = _root()
    staging = None
    try:
        # A unique directory, never shared or addressed by a caller, prevents
        # name collisions and overwriting any existing artifact file.
        directory = Path(tempfile.mkdtemp(prefix="bid-export-", dir=root))
        staging = directory / "pending"
        final = directory / "artifact"
        with staging.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        _verify(staging, digest, size)
        os.replace(staging, final)
        _verify(final, digest, size)
        return final.relative_to(root).as_posix()
    except (OSError, ValueError):
        raise ArtifactStorageError("Private artifact storage failed.") from None
    finally:
        if staging is not None:
            try:
                staging.unlink(missing_ok=True)
            except OSError:
                pass


def read_verified_artifact(key, digest, size):
    """Read only service-generated keys within the configured private root."""
    parts = key.split("/")
    if (len(parts) != 2 or not parts[0].startswith("bid-export-")
            or not re.fullmatch(r"[a-z0-9_]{8}", parts[0][11:]) or parts[1] != "artifact"):
        raise ArtifactStorageError("Artifact integrity check failed.")
    root = _root()
    path = root / parts[0] / parts[1]
    try:
        if path.parent.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
            raise ArtifactStorageError("Artifact integrity check failed.")
        return _verify(path, digest, size)
    except (OSError, ValueError):
        raise ArtifactStorageError("Artifact integrity check failed.") from None
