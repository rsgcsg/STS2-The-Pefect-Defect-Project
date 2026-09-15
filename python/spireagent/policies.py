"""Explicit trusted adapter composition; downloaded manifests cannot select arbitrary code."""

from types import ModuleType

from spireagent.json_boundary import BoundaryError

SUPPORTED_ADAPTERS = frozenset({"s1-v1"})


def policy_support(adapter: str) -> ModuleType:
    if adapter == "s1-v1":
        from stpd.policy import installation

        return installation
    raise BoundaryError("local_model", "unsupported_trusted_adapter")
