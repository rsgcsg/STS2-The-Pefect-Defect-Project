"""Bounded, process-local reuse of verified immutable model inputs.

The first load still performs the owning semantic reprojection. Hits re-read/hash the
whole artifact closure through ArtifactStore, but do not repeat JSON/semantic decoding.
This cache contains no permission, Gold reservation or mutable operational state.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

from spireagent.artifact_contracts import Manifest
from spireagent.json_boundary import BoundaryError
from spireagent.storage.store import ArtifactStore

if TYPE_CHECKING:
    from .features import ModelSample


@dataclass
class ViewSession:
    store: ArtifactStore
    identity: str | None = None
    value: tuple[Manifest, tuple[ModelSample, ...]] | None = None
    hits: int = 0
    misses: int = 0


_CURRENT: ContextVar[ViewSession | None] = ContextVar("verified_model_views", default=None)


@contextmanager
def verified_model_views(store: ArtifactStore) -> Iterator[ViewSession]:
    """Opt in for one owner command; nested/task contexts restore their prior scope."""
    session = ViewSession(store)
    token = _CURRENT.set(session)
    try:
        yield session
    finally:
        _CURRENT.reset(token)


def load_view(
    store: ArtifactStore,
    identity: str,
    loader: Callable[[ArtifactStore, str], tuple[Manifest, tuple[ModelSample, ...]]],
) -> tuple[Manifest, tuple[ModelSample, ...]]:
    session = _CURRENT.get()
    if session is None or session.store is not store:
        return loader(store, identity)
    if session.identity == identity and session.value is not None:
        # Parent IDs and payload digests are content-bound by each checked manifest.
        # A hit cannot conceal a missing/corrupt original, allocation or view payload.
        pending = [identity]
        seen: set[str] = set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            if len(seen) >= 512:
                raise BoundaryError("view_session", "lineage_limit")
            seen.add(current)
            manifest = store.get_manifest(current)
            for payload in manifest.payloads:
                for _ in store.read_payload(payload):
                    pass
            pending.extend(parent.artifact_id for parent in manifest.parents)
        session.hits += 1
        return session.value
    value = loader(store, identity)
    # Retain at most one already-loaded immutable view; no full source/feature matrix.
    session.identity, session.value = identity, value
    session.misses += 1
    return value
