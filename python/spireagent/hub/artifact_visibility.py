"""Personal archival overlay; immutable artifacts, lineage and use ledgers survive."""

from __future__ import annotations

from spireagent.hub.collections import CollectionAccess
from spireagent.hub.console_auth import ConsolePrincipal
from spireagent.hub.uploads import UploadService
from spireagent.json_boundary import BoundaryError, digest, object_fields


class ArtifactVisibility:
    def __init__(self, service: UploadService) -> None:
        self.service = service
        self.collections = CollectionAccess(service)

    def write(self, principal: ConsolePrincipal, body: object) -> dict:
        self.collections.require_member(principal)
        value = object_fields(body, {"ids", "archived"}, "artifact_visibility")
        ids = value["ids"]
        if (
            not isinstance(ids, list)
            or not 1 <= len(ids) <= 100
            or type(value["archived"]) is not bool
        ):
            raise BoundaryError("artifact_visibility", "invalid_request")
        checked = sorted({digest(i, "artifact_visibility.id") for i in ids})
        for identity in checked:
            item = self.collections.artifact(identity)
            if item.kind == "run" and value["archived"]:
                with self.service.operations.transaction() as db:
                    rows = db.execute(
                        "SELECT a.artifact_id FROM console_artifacts a JOIN console_lineage l "
                        "ON l.child=a.artifact_id WHERE a.kind='run_result' AND l.parent=?",
                        (identity,),
                    ).fetchall()
                results = [self.service.store.get_manifest(row[0]) for row in rows]
                if not any(
                    r.parent("run") == identity and r.parameters.value().get("state") == "completed"
                    for r in results
                ):
                    raise BoundaryError("artifact_visibility", "unfinished_run_cannot_archive")
        with self.service.operations.transaction() as db:
            db.executemany(
                "INSERT OR REPLACE INTO console_artifact_visibility VALUES(?,?,?)",
                [(i, principal.subject, int(value["archived"])) for i in checked],
            )
            for identity in checked:
                self.service.operations._event(
                    db,
                    principal.subject,
                    "artifact_visibility",
                    identity,
                    {"archived": value["archived"]},
                )
        return {"ids": checked, "archived": value["archived"], "effect": "personal_list_only"}
