"""Bounded Human administration; membership services retain transactional authority."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs

from ..json_boundary import BoundaryError
from .console_auth import ConsolePrincipal
from .identity import IdentityService


class MemberAdministration:
    def __init__(self, identity: IdentityService) -> None:
        self.identity = identity

    def read(self, path: str, query: str, principal: ConsolePrincipal) -> dict[str, Any]:
        if principal.role != "admin":
            raise BoundaryError("membership", "admin_required")
        values = parse_qs(query, strict_parsing=True, max_num_fields=2)
        if set(values) - {"limit", "offset"} or any(len(v) != 1 for v in values.values()):
            raise BoundaryError("membership", "invalid_admin_query")
        limit, offset = int(values.get("limit", ["25"])[0]), int(values.get("offset", ["0"])[0])
        if not 1 <= limit <= 100 or offset < 0:
            raise BoundaryError("membership", "invalid_admin_query")
        if path == "members":
            return self.identity.membership.list(principal, limit=limit, offset=offset)
        raise BoundaryError("membership", "resource_not_found")

    def write(
        self, path: str, value: dict[str, Any], principal: ConsolePrincipal
    ) -> dict[str, Any]:
        # The owning service repeats current role/active checks inside the transaction.
        # This route is reachable only after browser JWT, exact Origin and CSRF checks.
        if principal.role != "admin":
            raise BoundaryError("membership", "admin_required")
        service = self.identity.membership
        if path == "members":
            return service.invite(principal, value)
        member = re.fullmatch(r"members/([a-f0-9]{32})(?:/(revoke-sessions))?", path)
        if member:
            if member[2]:
                if value:
                    raise BoundaryError("membership", "invalid_admin_request")
                return service.revoke_sessions(principal, member[1])
            return service.update(principal, member[1], value)
        device = re.fullmatch(r"devices/([A-Za-z0-9_.-]{1,128})/revoke", path)
        if device and not value:
            return service.revoke_device(principal, device[1])
        raise BoundaryError("membership", "resource_not_found")
