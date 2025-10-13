"""Resource template registration utilities for OpenMCP.

Follows ``docs/mcp/spec/schema-reference/resources-templates-list.md``.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from collections.abc import Iterable, Mapping

from . import types

if types:  # pragma: no cover
    types.ResourceTemplate  # noqa: B018

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .server import MCPServer


@dataclass(slots=True)
class ResourceTemplateSpec:
    name: str
    uri_template: str
    description: str | None = None
    mime_type: str | None = None
    icons: list[types.Icon] | None = None
    meta: Mapping[str, object] | None = None

    def to_resource_template(self) -> types.ResourceTemplate:
        return types.ResourceTemplate(
            name=self.name,
            title=None,
            uriTemplate=self.uri_template,
            description=self.description,
            mimeType=self.mime_type,
            icons=self.icons,
            meta=dict(self.meta) if self.meta is not None else None,
        )


_TEMPLATE_ATTR = "__openmcp_resource_template__"
_ACTIVE_SERVER: ContextVar["MCPServer | None"] = ContextVar(
    "_openmcp_resource_template_server",
    default=None,
)


def get_active_server() -> "MCPServer | None":
    return _ACTIVE_SERVER.get()


def set_active_server(server: "MCPServer") -> object:
    return _ACTIVE_SERVER.set(server)


def reset_active_server(token: object) -> None:
    _ACTIVE_SERVER.reset(token)


def resource_template(
    name: str,
    *,
    uri_template: str,
    description: str | None = None,
    mime_type: str | None = None,
    icons: Iterable[Mapping[str, object]] | None = None,
    meta: Mapping[str, object] | None = None,
):
    """Register metadata for a resource template.

    Mirrors ``resources/templates/list`` requirements.

    """
    icon_list = [types.Icon(**icon) for icon in icons] if icons else None

    def decorator(fn):
        spec = ResourceTemplateSpec(
            name=name,
            uri_template=uri_template,
            description=description,
            mime_type=mime_type,
            icons=icon_list,
            meta=meta,
        )
        setattr(fn, _TEMPLATE_ATTR, spec)

        server = get_active_server()
        if server is not None:
            server.register_resource_template(spec)
        return fn

    return decorator


def extract_resource_template_spec(obj) -> ResourceTemplateSpec | None:
    spec = getattr(obj, _TEMPLATE_ATTR, None)
    if isinstance(spec, ResourceTemplateSpec):
        return spec
    return None


__all__ = [
    "resource_template",
    "ResourceTemplateSpec",
    "extract_resource_template_spec",
    "set_active_server",
    "reset_active_server",
]
