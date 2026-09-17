"""Private disk-backed decision rows; never an admission or public artifact format."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from collections.abc import Iterator, MutableMapping, Sequence
from pathlib import Path
from typing import overload

from spireagent.json_boundary import BoundaryError

from .contracts import ResearchTransitionV2


class DecisionSpool(MutableMapping[str, ResearchTransitionV2]):
    """Keep large state/action/Read payloads off the aggregate selection heap.

    The returned selection retains this owner until consumers finish publishing.
    Temporary files are private and removed with the owner; no evidence is stored here.
    """

    def __init__(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="stpd-decision-rows-")
        self.db = sqlite3.connect(Path(self.directory.name) / "rows.sqlite")
        self.db.execute("PRAGMA cache_size=-2048")
        self.db.execute("PRAGMA temp_store=FILE")
        self.db.execute("CREATE TABLE records(id TEXT PRIMARY KEY,run TEXT,sequence INTEGER,"
                        "body TEXT NOT NULL,selected INTEGER NOT NULL DEFAULT 0)")

    def __getitem__(self, key: str) -> ResearchTransitionV2:
        row = self.db.execute("SELECT body FROM records WHERE id=?", (key,)).fetchone()
        if row is None:
            raise KeyError(key)
        return ResearchTransitionV2.decode(json.loads(row[0]))

    def __setitem__(self, key: str, value: ResearchTransitionV2) -> None:
        self.db.execute("INSERT OR REPLACE INTO records(id,run,sequence,body) VALUES(?,?,?,?)",
                        (key, value.run_id, value.source_evidence.value()["action_sequence"],
                         json.dumps(value.to_dict(), separators=(",", ":"))))

    def __delitem__(self, key: str) -> None:
        if not self.db.execute("DELETE FROM records WHERE id=?", (key,)).rowcount:
            raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        for row in self.db.execute("SELECT id FROM records ORDER BY id"):
            yield row[0]

    def __len__(self) -> int:
        return int(self.db.execute("SELECT count(*) FROM records").fetchone()[0])

    def select(self, key: str) -> None:
        self.db.execute("UPDATE records SET selected=1 WHERE id=?", (key,))

    def selected(self) -> SpoolSelection:
        self.db.commit()
        return SpoolSelection(self)

    def close(self) -> None:
        self.db.close()
        self.directory.cleanup()

    def __del__(self) -> None:
        if hasattr(self, "db"):
            self.close()


class SpoolSelection(Sequence[ResearchTransitionV2]):
    def __init__(self, owner: DecisionSpool) -> None:
        self.owner = owner
        self.size = int(owner.db.execute(
            "SELECT count(*) FROM records WHERE selected=1").fetchone()[0])

    def __len__(self) -> int:
        return self.size

    def __iter__(self) -> Iterator[ResearchTransitionV2]:
        for row in self.owner.db.execute(
            "SELECT body FROM records WHERE selected=1 ORDER BY run,sequence,id"
        ):
            yield ResearchTransitionV2.decode(json.loads(row[0]))

    @overload
    def __getitem__(self, index: int) -> ResearchTransitionV2: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[ResearchTransitionV2, ...]: ...

    def __getitem__(
        self, index: int | slice,
    ) -> ResearchTransitionV2 | tuple[ResearchTransitionV2, ...]:
        if isinstance(index, slice):
            return tuple(self[i] for i in range(*index.indices(len(self))))
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        row = self.owner.db.execute(
            "SELECT body FROM records WHERE selected=1 ORDER BY run,sequence,id LIMIT 1 OFFSET ?",
            (index,),
        ).fetchone()
        if row is None:
            raise BoundaryError("decision_spool", "selection_changed")
        return ResearchTransitionV2.decode(json.loads(row[0]))

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, Sequence) and len(self) == len(other)
                and all(a == b for a, b in zip(self, other, strict=True)))
