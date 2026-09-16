"""Read-only cloud console routes; no raw artifact reads or research work on GET."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode

from spireagent.hub.backup_status import freshness as backup_freshness
from spireagent.hub.backup_status import project as project_backup_status
from spireagent.hub.capacity import filesystem_capacity
from spireagent.hub.console_auth import ConsolePrincipal
from spireagent.hub.console_index import SCHEMA, pagination, timestamp
from spireagent.hub.uploads import UploadService
from spireagent.json_boundary import BoundaryError


class ConsoleRoutes:
    def __init__(
        self,
        service: UploadService,
        budget_limit: int,
        *,
        backup_status: Path | None = None,
        browser_enabled: bool = False,
    ) -> None:
        self.service, self.budget_limit, self.backup_status = service, budget_limit, backup_status
        self.browser_enabled = browser_enabled

    def system(self, principal: ConsolePrincipal) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema": SCHEMA,
            "observed_at": timestamp(),
            "access": principal.public(),
            "producer": self.service.producer.to_dict(),
            "compute": {
                "budget_units": self.budget_limit,
                "budget_allows_reservations": self.budget_limit > 0,
                "paused": self.service.operations.paused(),
            },
            "browser_auth": "cloudflare_access_application_jwt",
            "browser_access_configured": self.browser_enabled,
            "terminal_presence": "not_observed",
            "raw_downloads": "explicit_project_sharing_grant_required",
            "backup": {"availability": "not_authorized"},
            "external_alerting": "not_qualified",
            "whole_host_recovery": "not_qualified",
        }
        if principal.role in {"operator", "admin"}:
            capacity = filesystem_capacity(self.service.operations.path.parent)
            result["storage"] = {
                "total_bytes": capacity["total_bytes"],
                "free_bytes": capacity["free_bytes"],
                "scope": "hub_state_filesystem",
                "capacity": capacity,
            }
            result["backup"] = self.backup()
            result["projection"] = self.service.console_index.health()
        return result

    def backup(self) -> dict[str, Any]:
        path = self.backup_status
        if path is None:
            return {"availability": "not_configured"}
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
                raise ValueError
            value = json.loads(path.read_bytes())
            safe = project_backup_status(value)
            return {
                "availability": "available", "scope": "operations_database_backup",
                **safe, **backup_freshness(safe),
                "external_notification": "not_configured_by_this_tool",
            }

        except (OSError, ValueError, TypeError, AttributeError):
            return {"availability": "unavailable", "error": "backup_status_unreadable"}

    def read(self, resource: str, query: str, principal: ConsolePrincipal) -> dict[str, Any]:
        search = ""
        if resource == "datasets":
            try:
                pairs = parse_qsl(query, strict_parsing=True, keep_blank_values=True,
                                  max_num_fields=4)
                searches = [v for k, v in pairs if k == "q"]
                if len(searches) > 1 or any(len(v) > 100 for v in searches):
                    raise ValueError
                search = searches[0].strip() if searches else ""
                query = urlencode([(k, v) for k, v in pairs if k != "q"])
            except ValueError:
                raise BoundaryError("console", "invalid_dataset_search") from None
        limit, offset, status = pagination(query)
        index = self.service.console_index
        if resource == "collections":
            return index.collections(principal, limit=limit, offset=offset, status=status)
        if re.fullmatch(r"collections/[a-f0-9]{32}", resource):
            if query:
                raise BoundaryError("console", "unexpected_query")
            return index.collections(principal, limit=1, offset=0, upload_id=resource.split("/")[1])
        if status is not None:
            raise BoundaryError("console", "status_filter_requires_collections")
        if re.fullmatch(r"(datasets|models|training|evaluations|analyses)/[a-f0-9]{64}", resource):
            if query:
                raise BoundaryError("console", "unexpected_query")
            kind, artifact_id = resource.split("/")
            return index.artifacts(principal, kind, limit=1, offset=0, artifact_id=artifact_id)
        if resource in {"datasets", "models", "training", "evaluations", "analyses"}:
            return index.artifacts(principal, resource, limit=limit, offset=offset, search=search)
        if resource == "statistics":
            if query:
                raise BoundaryError("console", "unexpected_query")
            return index.statistics(principal)
        if resource == "jobs":
            return index.jobs(limit=limit, offset=offset)
        if resource == "system":
            if query:
                raise BoundaryError("console", "unexpected_query")
            return self.system(principal)
        if resource == "overview":
            if query:
                raise BoundaryError("console", "unexpected_query")
            return {
                "schema": SCHEMA,
                "observed_at": timestamp(),
                "access": principal.public(),
                "counts": index.counts(principal),
                "latest": index.collections(principal, limit=3, offset=0)["items"],
                "compute": {
                    "budget_units": self.budget_limit,
                    "paused": self.service.operations.paused(),
                },
                "terminal_presence": "not_observed",
            }
        raise BoundaryError("console", "resource_not_found")
