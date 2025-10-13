"""High-level server primitives built on the reference SDK.

The implementation follows the MCP lifecycle defined in
``docs/mcp/core/lifecycle/lifecycle-phases.md`` and the capability metadata
outlined in the feature-specific documents under ``docs/mcp/capabilities``.

This module now implements the ambient registration pattern discussed in the DX
conversation: developers author plain functions with ``@tool`` and register
those functions inside a short ``collecting`` scope.  The server then exposes
those callables both as Python attributes and via the MCP ``tools/list`` and
``tools/call`` RPCs (see
``docs/mcp/spec/schema-reference/tools-list.md`` and
``docs/mcp/spec/schema-reference/tools-call.md``).
"""

from __future__ import annotations

import inspect
import json
import types as pytypes
import weakref
from collections import defaultdict
from contextlib import asynccontextmanager
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, NotRequired, TypedDict, TYPE_CHECKING

import anyio
from pydantic import TypeAdapter

from .._sdk_loader import ensure_sdk_importable

ensure_sdk_importable()

import mcp.types as types
from mcp.server.lowlevel.server import (
    NotificationOptions,
    Server,
    lifespan as default_lifespan,
    request_ctx,
)
from mcp.server.models import InitializationOptions
from mcp.shared.exceptions import McpError

from ..tool import (
    ToolSpec,
    extract_tool_spec,
    reset_active_server as reset_tool_server,
    set_active_server as set_tool_server,
)
from ..resource import (
    ResourceSpec,
    extract_resource_spec,
    reset_active_server as reset_resource_server,
    set_active_server as set_resource_server,
)
from ..completion import (
    CompletionResult,
    CompletionSpec,
    extract_completion_spec,
    reset_active_server as reset_completion_server,
    set_active_server as set_completion_server,
)
from ..prompt import (
    PromptSpec,
    extract_prompt_spec,
    reset_active_server as reset_prompt_server,
    set_active_server as set_prompt_server,
)
from ..resource_template import (
    ResourceTemplateSpec,
    extract_resource_template_spec,
    reset_active_server as reset_resource_template_server,
    set_active_server as set_resource_template_server,
)
from ..utils import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from mcp.shared.context import RequestContext
    from mcp.server.session import ServerSession


@dataclass(slots=True)
class NotificationFlags:
    """Notifications advertised during initialization.

    The MCP specification makes list change notifications optional.  Each flag
    toggles the corresponding ``listChanged`` capability described in:

    * ``docs/mcp/capabilities/prompts/capabilities.md``
    * ``docs/mcp/capabilities/resources/capabilities.md``
    * ``docs/mcp/capabilities/tools/capabilities.md``
    """

    prompts_changed: bool = False
    resources_changed: bool = False
    tools_changed: bool = False


class MCPServer(Server[Any, Any]):
    """Spec-aligned server surface for MCP applications.

    The class extends the reference ``mcp`` server to provide:

    * lifecycle helpers that always advertise capabilities consistent with the
      MCP handshake (``docs/mcp/core/lifecycle/lifecycle-phases.md``)
    * the ambient tool registration UX discussed in the design notes
    * capability computation that respects optional resource subscriptions as
      documented in ``docs/mcp/spec/schema-reference/resources-subscribe.md``
    """

    def __init__(
        self,
        name: str,
        *,
        version: str | None = None,
        instructions: str | None = None,
        website_url: str | None = None,
        icons: list[types.Icon] | None = None,
        notification_flags: NotificationFlags | None = None,
        experimental_capabilities: Mapping[str, Mapping[str, Any]] | None = None,
        lifespan: Callable[[Server[Any, Any]], Any] = default_lifespan,
        transport: str | None = None,
    ) -> None:
        self._notification_flags = notification_flags or NotificationFlags()
        self._experimental_capabilities = {
            key: dict(value) for key, value in (experimental_capabilities or {}).items()
        }
        super().__init__(
            name,
            version=version,
            instructions=instructions,
            website_url=website_url,
            icons=icons,
            lifespan=lifespan,
        )
        self._default_transport = transport.lower() if transport else "streamable-http"
        self._logger = get_logger(f"openmcp.server.{name}")
        self._tool_specs: dict[str, ToolSpec] = {}
        self._tool_defs: dict[str, types.Tool] = {}
        self._attached_names: set[str] = set()
        self._allow: set[str] | None = None

        self._resource_specs: dict[str, ResourceSpec] = {}
        self._resource_defs: dict[str, types.Resource] = {}

        self._completion_specs: dict[tuple[str, str], CompletionSpec] = {}
        self._prompt_specs: dict[str, PromptSpec] = {}
        self._prompt_defs: dict[str, types.Prompt] = {}
        self._resource_template_specs: dict[str, ResourceTemplateSpec] = {}
        self._resource_template_defs: list[types.ResourceTemplate] = []
        self._tools_observers: weakref.WeakSet[Any] = weakref.WeakSet()
        self._resources_observers: weakref.WeakSet[Any] = weakref.WeakSet()
        self._prompts_observers: weakref.WeakSet[Any] = weakref.WeakSet()
        self._pagination_limit = 50

        self._resource_subscribers: dict[str, weakref.WeakSet[Any]] = defaultdict(weakref.WeakSet)
        self._session_resource_map: weakref.WeakKeyDictionary[Any, set[str]] = weakref.WeakKeyDictionary()
        self._resource_subscription_lock = anyio.Lock()

        @self.list_resources()
        async def _list_resources(request: types.ListResourcesRequest) -> types.ListResourcesResult:
            cursor = request.params.cursor if request.params is not None else None
            resources = list(self._resource_defs.values())
            page, next_cursor = self._paginate(resources, cursor)
            self._remember_observer(self._resources_observers)
            return types.ListResourcesResult(resources=page, nextCursor=next_cursor)

        @self.read_resource()
        async def _read_resource(request: types.ReadResourceRequest) -> types.ReadResourceResult:
            return await self._execute_resource(request.params.uri)

        async def _list_resource_templates(request: types.ListResourceTemplatesRequest) -> types.ServerResult:
            cursor = request.params.cursor if request.params is not None else None
            page, next_cursor = self._paginate(self._resource_template_defs, cursor)
            return types.ServerResult(
                types.ListResourceTemplatesResult(resourceTemplates=page, nextCursor=next_cursor)
            )

        self.request_handlers[types.ListResourceTemplatesRequest] = _list_resource_templates

        # Install default handlers so tools/list and tools/call work immediately.
        @self.list_tools()
        async def _list_tools(request: types.ListToolsRequest) -> types.ListToolsResult:
            cursor = request.params.cursor if request.params is not None else None
            tools = list(self._tool_defs.values())
            page, next_cursor = self._paginate(tools, cursor)
            self._remember_observer(self._tools_observers)
            return types.ListToolsResult(tools=page, nextCursor=next_cursor)

        @self.call_tool(validate_input=False)
        async def _call_tool(name: str, arguments: dict[str, Any] | None) -> types.CallToolResult:
            return await self._execute_tool(name, arguments or {})

        @self.completion()
        async def _completion_handler(
            ref: types.PromptReference | types.ResourceTemplateReference,
            argument: types.CompletionArgument,
            context: types.CompletionContext | None,
        ) -> types.Completion | None:
            return await self._execute_completion(ref, argument, context)

        @self.subscribe_resource()
        async def _subscribe(uri: Any) -> None:
            await self._handle_resource_subscribe(str(uri))

        @self.unsubscribe_resource()
        async def _unsubscribe(uri: Any) -> None:
            await self._handle_resource_unsubscribe(str(uri))

        @self.list_prompts()
        async def _list_prompts(request: types.ListPromptsRequest) -> types.ListPromptsResult:
            cursor = request.params.cursor if request.params is not None else None
            prompts = list(self._prompt_defs.values())
            page, next_cursor = self._paginate(prompts, cursor)
            self._remember_observer(self._prompts_observers)
            return types.ListPromptsResult(prompts=page, nextCursor=next_cursor)

        @self.get_prompt()
        async def _get_prompt(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
            return await self._execute_prompt(name, arguments)

        self._call_tool_handler = _call_tool
        self._refresh_tools()
        self._refresh_resources()
        self._refresh_prompts()
        self._refresh_resource_templates()

    # ------------------------------------------------------------------
    # Capability negotiation helpers
    # ------------------------------------------------------------------

    def create_initialization_options(
        self,
        *,
        notification_flags: NotificationFlags | None = None,
        experimental_capabilities: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> InitializationOptions:
        """Build the options payload for ``initialize``.

        This mirrors the "Initialization" phase specified in
        ``docs/mcp/core/lifecycle/lifecycle-phases.md`` and guarantees that the
        advertised capabilities match registered handlers.
        """

        flags = notification_flags or self._notification_flags
        experimental = experimental_capabilities or self._experimental_capabilities

        return super().create_initialization_options(
            notification_options=NotificationOptions(
                prompts_changed=flags.prompts_changed,
                resources_changed=flags.resources_changed,
                tools_changed=flags.tools_changed,
            ),
            experimental_capabilities={key: dict(value) for key, value in experimental.items()},
        )

    def get_capabilities(
        self,
        notification_options: NotificationOptions,
        experimental_capabilities: Mapping[str, Mapping[str, Any]],
    ) -> types.ServerCapabilities:
        caps = super().get_capabilities(notification_options, experimental_capabilities)

        if caps.resources is not None:
            subscribe_supported = (
                types.SubscribeRequest in self.request_handlers
                and types.UnsubscribeRequest in self.request_handlers
            )
            caps.resources.subscribe = subscribe_supported

        if caps.prompts is not None and self._notification_flags.prompts_changed:
            caps.prompts.listChanged = True

        if caps.tools is not None and self._notification_flags.tools_changed:
            caps.tools.listChanged = True

        return caps

    # ------------------------------------------------------------------
    # Tool registration API
    # ------------------------------------------------------------------

    @contextmanager
    def collecting(self):
        """Ambient scope for ``@tool`` registration.

        Sample usage::

            server = MCPServer(...)
            with server.collecting():
                @tool(description="Adds numbers")
                def add(a: int, b: int) -> int:
                    return a + b

        Outside the scope the decorator simply stores metadata on the function.
        This allows plugin packages to be imported without an active server.

        """
        tool_token = set_tool_server(self)
        resource_token = set_resource_server(self)
        completion_token = set_completion_server(self)
        prompt_token = set_prompt_server(self)
        template_token = set_resource_template_server(self)

        try:
            yield self
        finally:
            reset_tool_server(tool_token)
            reset_resource_server(resource_token)
            reset_completion_server(completion_token)
            reset_prompt_server(prompt_token)
            reset_resource_template_server(template_token)
            self._refresh_tools()
            self._refresh_resources()
            self._refresh_prompts()
            self._refresh_resource_templates()

    def register_tool(self, target: ToolSpec | Callable[..., Any]) -> ToolSpec:
        """Register *target* as a tool.

        ``target`` may be a :class:`ToolSpec` (used internally by the decorator)
        or a plain callable carrying the metadata attribute.  If no metadata is
        present a basic spec is generated using the function name.

        """
        spec = target if isinstance(target, ToolSpec) else extract_tool_spec(target)  # type: ignore[arg-type]
        if spec is None:
            fn = target  # type: ignore[assignment]
            spec = ToolSpec(name=getattr(fn, "__name__", "anonymous"), fn=fn)
        # Store latest spec and rebuild exposed tools.
        self._tool_specs[spec.name] = spec
        self._refresh_tools()
        return spec

    def register_resource(self, target: ResourceSpec | Callable[[], str | bytes]) -> ResourceSpec:
        spec = target if isinstance(target, ResourceSpec) else extract_resource_spec(target)  # type: ignore[arg-type]
        if spec is None:
            fn = target  # type: ignore[assignment]
            raise ValueError("Resource functions must be decorated with @resource")
        self._resource_specs[spec.uri] = spec
        self._refresh_resources()
        return spec

    async def notify_resource_updated(self, uri: str) -> None:
        """Emit ``notifications/resources/updated`` to active subscribers.

        Matches the behaviour required by
        ``docs/mcp/spec/schema-reference/notifications-resources-updated.md``.
        """
        async with self._resource_subscription_lock:
            subscribers = list(self._resource_subscribers.get(uri, ()))

        if not subscribers:
            return

        notification = types.ServerNotification(
            types.ResourceUpdatedNotification(
                params=types.ResourceUpdatedNotificationParams(uri=uri),
            )
        )

        stale_sessions: list[Any] = []
        for session in subscribers:
            try:
                await session.send_notification(notification)
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.warning("Failed to notify subscriber for %s: %s", uri, exc)
                stale_sessions.append(session)

        if stale_sessions:
            async with self._resource_subscription_lock:
                for session in stale_sessions:
                    subscribers_set = self._resource_subscribers.get(uri)
                    if subscribers_set is not None:
                        subscribers_set.discard(session)

    def register_prompt(self, target: PromptSpec | Callable[..., Any]) -> PromptSpec:
        """Register a prompt renderer.

        Mirrors the prompt metadata rules in
        ``docs/mcp/capabilities/prompts/data-types.md``.
        """

        spec = target if isinstance(target, PromptSpec) else extract_prompt_spec(target)  # type: ignore[arg-type]
        if spec is None:
            raise ValueError("Prompt functions must be decorated with @prompt")
        self._prompt_specs[spec.name] = spec
        self._refresh_prompts()
        return spec

    def register_resource_template(
        self,
        target: ResourceTemplateSpec | Callable[..., Any],
    ) -> ResourceTemplateSpec:
        """Register a resource template (``resources/templates/list``)."""

        spec = (
            target
            if isinstance(target, ResourceTemplateSpec)
            else extract_resource_template_spec(target)  # type: ignore[arg-type]
        )
        if spec is None:
            raise ValueError("Resource templates must be decorated with @resource_template")
        self._resource_template_specs[spec.uri_template] = spec
        self._refresh_resource_templates()
        return spec

    def register_completion(
        self,
        target: CompletionSpec | Callable[..., Any],
    ) -> CompletionSpec:
        """Register a completion provider (``completion/complete``).

        Refer to ``docs/mcp/capabilities/completion/protocol-messages.md`` for
        the mapping between prompt/resource references and handlers.
        """

        spec = (
            target
            if isinstance(target, CompletionSpec)
            else extract_completion_spec(target)  # type: ignore[arg-type]
        )
        if spec is None:
            raise ValueError("Completion functions must be decorated with @completion")
        self._completion_specs[(spec.ref_type, spec.key)] = spec
        return spec

    def allow_tools(self, names: Iterable[str] | None) -> None:
        """Restrict the active tool set to *names* (``None`` => allow all)."""

        self._allow = set(names) if names is not None else None
        self._refresh_tools()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _execute_tool(self, name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        spec = self._tool_specs.get(name)
        if not spec or name not in self._tool_defs:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f'Tool "{name}" is not available')],
                isError=True,
            )

        call_target = spec.fn
        try:
            result = call_target(**arguments)
        except TypeError as exc:  # argument mismatch
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Invalid arguments: {exc}")],
                isError=True,
            )

        if inspect.isawaitable(result):
            result = await result  # type: ignore[assignment]

        if isinstance(result, types.CallToolResult):
            return result

        if isinstance(result, types.ServerResult):
            raise RuntimeError(
                "Tool returned types.ServerResult; return the nested CallToolResult instead."
            )

        if isinstance(result, str):
            text = result
        else:
            try:
                text = json.dumps(result, ensure_ascii=False)
            except Exception:
                text = str(result)

        return types.CallToolResult(
            content=[types.TextContent(type="text", text=text)],
        )

    async def _execute_resource(self, uri: str) -> types.ReadResourceResult:
        spec = self._resource_specs.get(uri)
        if spec is None or uri not in self._resource_defs:
            return types.ReadResourceResult(contents=[])

        try:
            data = spec.fn()
        except Exception as exc:  # pragma: no cover - defensive
            text = f"Resource error: {exc}"
            return types.ReadResourceResult(
                contents=[
                    types.TextResourceContents(
                        uri=uri,
                        name=spec.name or uri,
                        text=text,
                        mimeType="text/plain",
                    )
                ]
            )

        if isinstance(data, bytes):
            import base64

            return types.ReadResourceResult(
                contents=[
                    types.BlobResourceContents(
                        uri=uri,
                        name=spec.name or uri,
                        blob=base64.b64encode(data).decode(),
                        mimeType=spec.mime_type or "application/octet-stream",
                    )
                ]
            )

        return types.ReadResourceResult(
            contents=[
                types.TextResourceContents(
                    uri=uri,
                    name=spec.name or uri,
                    text=str(data),
                    mimeType=spec.mime_type or "text/plain",
                )
            ]
        )

    async def _execute_completion(
        self,
        ref: types.PromptReference | types.ResourceTemplateReference,
        argument: types.CompletionArgument,
        context: types.CompletionContext | None,
    ) -> types.Completion | None:
        spec = self._get_completion_spec(ref)
        if spec is None:
            return types.Completion(values=[], total=None, hasMore=None)

        result = spec.fn(argument, context)
        if inspect.isawaitable(result):
            result = await result  # type: ignore[assignment]

        return self._coerce_completion(result)

    async def _handle_resource_subscribe(self, uri: str) -> None:
        context = self._get_request_context()
        if context is None:
            raise RuntimeError("resources/subscribe called without request context")

        session = context.session
        async with self._resource_subscription_lock:
            subscribers = self._resource_subscribers[uri]
            subscribers.add(session)
            session_uris = self._session_resource_map.setdefault(session, set())
            session_uris.add(uri)

    async def _handle_resource_unsubscribe(self, uri: str) -> None:
        context = self._get_request_context()
        if context is None:
            return

        session = context.session
        async with self._resource_subscription_lock:
            subscribers = self._resource_subscribers.get(uri)
            if subscribers is not None:
                subscribers.discard(session)
                if not subscribers:
                    self._resource_subscribers.pop(uri, None)

            session_uris = self._session_resource_map.get(session)
            if session_uris is not None:
                session_uris.discard(uri)
                if not session_uris:
                    try:
                        del self._session_resource_map[session]
                    except KeyError:
                        pass

    def _refresh_tools(self) -> None:
        # Remove previously attached attributes
        for name in list(self._attached_names):
            if hasattr(self, name):
                try:
                    delattr(self, name)
                except AttributeError:
                    pass
        self._attached_names.clear()
        self._tool_defs.clear()

        for spec in self._tool_specs.values():
            if not self._is_tool_enabled(spec):
                continue

            tool_def = types.Tool(
                name=spec.name,
                description=spec.description or None,
                inputSchema=spec.input_schema or self._build_input_schema(spec.fn),
            )
            self._tool_defs[spec.name] = tool_def
            setattr(self, spec.name, spec.fn)
            self._attached_names.add(spec.name)

    def _refresh_resources(self) -> None:
        self._resource_defs.clear()
        for spec in self._resource_specs.values():
            self._resource_defs[spec.uri] = types.Resource(
                uri=spec.uri,
                name=spec.name or spec.uri,
                description=spec.description,
                mimeType=spec.mime_type,
            )

    def _refresh_prompts(self) -> None:
        self._prompt_defs.clear()
        for spec in self._prompt_specs.values():
            prompt = types.Prompt(
                name=spec.name,
                title=spec.title,
                description=spec.description,
                arguments=spec.arguments,
                icons=spec.icons,
                meta=dict(spec.meta) if spec.meta is not None else None,
            )
            self._prompt_defs[spec.name] = prompt

    def _refresh_resource_templates(self) -> None:
        self._resource_template_defs = [
            spec.to_resource_template()
            for spec in sorted(
                self._resource_template_specs.values(),
                key=lambda s: (s.name, s.uri_template),
            )
        ]

    def _is_tool_enabled(self, spec: ToolSpec) -> bool:
        if self._allow is not None and spec.name not in self._allow:
            return False
        if spec.enabled is not None and not spec.enabled(self):
            return False
        return True

    async def _execute_prompt(
        self,
        name: str,
        arguments: dict[str, str] | None,
    ) -> types.GetPromptResult:
        spec = self._prompt_specs.get(name)
        if spec is None:
            raise McpError(
                types.ErrorData(
                    code=types.INVALID_PARAMS,
                    message=f"Prompt '{name}' is not registered",
                )
            )

        provided = dict(arguments or {})
        missing = [arg.name for arg in (spec.arguments or []) if arg.required and arg.name not in provided]
        if missing:
            raise McpError(
                types.ErrorData(
                    code=types.INVALID_PARAMS,
                    message=f"Missing required arguments: {', '.join(sorted(missing))}",
                )
            )

        try:
            rendered = self._call_prompt_renderer(spec, provided)
            if inspect.isawaitable(rendered):
                rendered = await rendered  # type: ignore[assignment]
        except McpError:
            raise
        except Exception as exc:
            raise McpError(
                types.ErrorData(
                    code=types.INTERNAL_ERROR,
                    message=f"Prompt '{name}' failed: {exc}",
                )
            )

        return self._coerce_prompt_result(spec, rendered)

    def _call_prompt_renderer(
        self,
        spec: PromptSpec,
        provided: dict[str, str],
    ) -> Any:
        signature = inspect.signature(spec.fn)
        if len(signature.parameters) == 0:
            return spec.fn()
        return spec.fn(provided)

    def _coerce_prompt_result(self, spec: PromptSpec, result: Any) -> types.GetPromptResult:
        if isinstance(result, types.GetPromptResult):
            description = result.description or spec.description
            return types.GetPromptResult(messages=result.messages, description=description)

        if isinstance(result, Mapping):
            if "messages" not in result:
                raise TypeError("Prompt mapping must include 'messages'.")
            description = result.get("description", spec.description)
            messages = self._coerce_prompt_messages(result["messages"])
            return types.GetPromptResult(messages=messages, description=description)

        if result is None:
            messages = self._coerce_prompt_messages(())
            return types.GetPromptResult(messages=messages, description=spec.description)

        if isinstance(result, str):
            raise TypeError("Prompt renderer returned raw string; supply role + content.")

        if isinstance(result, Iterable):
            messages = self._coerce_prompt_messages(result)
            return types.GetPromptResult(messages=messages, description=spec.description)

        raise TypeError(f"Unsupported prompt return type: {type(result)!r}")

    def _coerce_prompt_messages(self, values: Any) -> list[types.PromptMessage]:
        if isinstance(values, types.PromptMessage):  # pragma: no cover - defensive
            return [values]
        messages: list[types.PromptMessage] = []
        if isinstance(values, Mapping):  # pragma: no cover - defensive
            values = [values]
        for item in list(values):
            messages.append(self._coerce_prompt_message(item))
        return messages

    def _coerce_prompt_message(self, item: Any) -> types.PromptMessage:
        if isinstance(item, types.PromptMessage):
            return item

        if isinstance(item, Mapping):
            role = item.get("role")
            content = item.get("content")
            if role is None or content is None:
                raise TypeError("Prompt message mapping requires 'role' and 'content'.")
            return types.PromptMessage(role=str(role), content=self._coerce_prompt_content(content))

        if isinstance(item, (tuple, list)) and len(item) == 2:
            role, content = item
            return types.PromptMessage(role=str(role), content=self._coerce_prompt_content(content))

        raise TypeError("Prompt message must be PromptMessage, mapping, or (role, content) tuple.")

    def _coerce_prompt_content(self, content: Any) -> types.ContentBlock:
        if isinstance(
            content,
            (
                types.TextContent,
                types.ImageContent,
                types.AudioContent,
                types.ResourceLink,
                types.EmbeddedResource,
            ),
        ):
            return content

        if isinstance(content, str):
            return types.TextContent(type="text", text=content)

        if isinstance(content, Mapping):
            content_type = content.get("type")
            if content_type == "text":
                return types.TextContent(**content)
            if content_type == "image":  # pragma: no cover - seldom used
                return types.ImageContent(**content)
            if content_type == "audio":  # pragma: no cover - seldom used
                return types.AudioContent(**content)
            if content_type == "resource":  # pragma: no cover - seldom used
                resource_payload = content.get("resource")
                if isinstance(resource_payload, Mapping):
                    try:
                        resource = types.TextResourceContents(**resource_payload)
                    except Exception:  # pragma: no cover - fallback to blob
                        resource = types.BlobResourceContents(**resource_payload)
                else:
                    raise TypeError("Embedded resource requires mapping payload.")
                return types.EmbeddedResource(type="resource", resource=resource)

        raise TypeError(f"Unsupported prompt content: {type(content)!r}")

    def _get_completion_spec(
        self,
        ref: types.PromptReference | types.ResourceTemplateReference,
    ) -> CompletionSpec | None:
        if isinstance(ref, types.PromptReference):
            return self._completion_specs.get(("prompt", ref.name))
        return self._completion_specs.get(("resource", ref.uri))

    def _coerce_completion(
        self,
        result: types.Completion
        | CompletionResult
        | Iterable[Any]
        | Mapping[str, Any]
        | None,
    ) -> types.Completion | None:
        if result is None:
            return None
        if isinstance(result, types.Completion):
            return self._enforce_completion_limit(result)
        if isinstance(result, CompletionResult):
            return self._build_completion(result.values, result.total, result.has_more)
        if isinstance(result, Mapping):
            values = result.get("values")
            if values is None:
                raise ValueError("Completion mapping must include 'values'.")
            total = result.get("total")
            has_more = result.get("hasMore", result.get("has_more"))
            return self._build_completion(values, total, has_more)
        if isinstance(result, str):
            return self._build_completion([result], None, None)
        if isinstance(result, Iterable):
            return self._build_completion(result, None, None)
        raise TypeError(f"Unsupported completion return type: {type(result)!r}")

    def _build_completion(
        self,
        values: Iterable[Any],
        total: int | None,
        has_more: bool | None,
    ) -> types.Completion:
        coerced = [str(value) for value in values]
        limited, limited_has_more = self._limit_values(coerced, has_more)
        return types.Completion(values=limited, total=total, hasMore=limited_has_more)

    def _enforce_completion_limit(self, completion: types.Completion) -> types.Completion:
        limited, has_more = self._limit_values(list(completion.values), completion.hasMore)
        return types.Completion(values=limited, total=completion.total, hasMore=has_more)

    def _limit_values(
        self,
        values: list[str],
        has_more: bool | None,
    ) -> tuple[list[str], bool | None]:
        limit = 100
        if len(values) <= limit:
            return values, has_more
        truncated = values[:limit]
        return truncated, True if has_more is None else has_more

    def _get_request_context(self) -> "RequestContext[ServerSession, Any, Any] | None":
        try:
            return request_ctx.get()
        except LookupError:
            return None

    def _paginate(
        self,
        items: list[Any],
        cursor: str | None,
        *,
        limit: int | None = None,
    ) -> tuple[list[Any], str | None]:
        if limit is None:
            limit = self._pagination_limit

        start = 0
        if cursor:
            try:
                start = max(0, int(cursor))
            except ValueError:
                raise McpError(
                    types.ErrorData(
                        code=types.INVALID_PARAMS,
                        message="Invalid cursor provided",
                    )
                )

        end = start + limit
        page = items[start:end]
        next_cursor = str(end) if end < len(items) else None
        return page, next_cursor

    def _build_input_schema(self, fn: Callable[..., Any]) -> dict[str, Any]:
        sig = inspect.signature(fn)
        annotations: dict[str, Any] = {}
        descriptions: dict[str, str] = {}

        default_values: dict[str, Any] = {}

        for name, param in sig.parameters.items():
            if param.kind not in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
                return {"type": "object"}

            annotation = param.annotation if param.annotation is not inspect._empty else Any
            descriptions[name] = f"Parameter {name}"

            if param.default is inspect._empty:
                annotations[name] = annotation
            else:
                annotations[name] = NotRequired[annotation]
                default_values[name] = param.default

        if not annotations:
            return {"type": "object", "properties": {}, "additionalProperties": False}

        namespace = {"__annotations__": annotations}
        typed_dict = pytypes.new_class(
            f"{fn.__name__.title()}ToolInput",
            (TypedDict,),
            {},
            lambda ns: ns.update(namespace),
        )

        try:
            schema = TypeAdapter(typed_dict).json_schema()
        except Exception:
            # Fallback to permissive schema if type adapter fails (e.g. unsupported annotations)
            return {"type": "object", "additionalProperties": True}

        schema.pop("$defs", None)

        properties = schema.setdefault("properties", {})
        for name, desc in descriptions.items():
            properties.setdefault(name, {})
            properties[name].setdefault("description", desc)
            if name in default_values:
                properties[name].setdefault("default", default_values[name])

        schema.setdefault("type", "object")
        schema["additionalProperties"] = False
        return schema

    # ------------------------------------------------------------------
    # Convenience helpers for tests / advanced users
    # ------------------------------------------------------------------

    @property
    def tool_names(self) -> list[str]:
        """Return the names of currently exposed tools."""

        return sorted(self._tool_defs)

    @property
    def prompt_names(self) -> list[str]:
        """Return registered prompt identifiers."""

        return sorted(self._prompt_defs)

    async def invoke_tool(self, name: str, **arguments: Any) -> types.CallToolResult:
        """Invoke a tool directly, bypassing JSON-RPC plumbing (useful for tests)."""

        return await self._execute_tool(name, arguments)

    async def invoke_resource(self, uri: str) -> types.ReadResourceResult:
        """Read a registered resource directly."""

        return await self._execute_resource(uri)

    async def invoke_completion(
        self,
        ref: types.PromptReference | types.ResourceTemplateReference,
        argument: types.CompletionArgument,
        context: types.CompletionContext | None = None,
    ) -> types.Completion | None:
        """Call a completion provider directly (test helper)."""

        return await self._execute_completion(ref, argument, context)

    async def invoke_prompt(
        self,
        name: str,
        *,
        arguments: dict[str, str] | None = None,
    ) -> types.GetPromptResult:
        """Render a prompt by name (test helper)."""

        return await self._execute_prompt(name, arguments)

    async def list_resource_templates_paginated(
        self,
        cursor: str | None = None,
    ) -> types.ListResourceTemplatesResult:
        """Retrieve resource templates using the server's pagination logic."""
        params = types.PaginatedRequestParams(cursor=cursor) if cursor is not None else None
        request = types.ListResourceTemplatesRequest(params=params)
        handler = self.request_handlers[types.ListResourceTemplatesRequest]
        server_result = await handler(request)
        if isinstance(server_result, types.ServerResult):
            return server_result.root
        return server_result

    # ------------------------------------------------------------------
    # Decorator passthroughs with spec references
    # ------------------------------------------------------------------

    def list_prompts(self):
        """Register a ``prompts/list`` handler (``docs/mcp/spec/schema-reference/prompts-list.md``)."""

        return super().list_prompts()

    def get_prompt(self):
        """Register a ``prompts/get`` handler (``docs/mcp/spec/schema-reference/prompts-get.md``)."""

        return super().get_prompt()

    def list_resources(self):
        """Register a ``resources/list`` handler (``docs/mcp/spec/schema-reference/resources-list.md``)."""

        return super().list_resources()

    def list_resource_templates(self):
        """Register a ``resources/templates/list`` handler (``docs/mcp/spec/schema-reference/resources-templates-list.md``)."""

        return super().list_resource_templates()

    def read_resource(self):
        """Register a ``resources/read`` handler (``docs/mcp/spec/schema-reference/resources-read.md``)."""

        return super().read_resource()

    def subscribe_resource(self):
        """Register ``resources/subscribe`` (``docs/mcp/spec/schema-reference/resources-subscribe.md``)."""

        return super().subscribe_resource()

    def unsubscribe_resource(self):
        """Register ``resources/unsubscribe`` (``docs/mcp/spec/schema-reference/resources-unsubscribe.md``)."""

        return super().unsubscribe_resource()

    def list_tools(self):  # type: ignore[override]
        """Expose decorator for custom ``tools/list`` handlers if needed."""

        return super().list_tools()

    def call_tool(self, *, validate_input: bool = True):  # type: ignore[override]
        """Expose decorator for custom ``tools/call`` handlers if needed."""

        return super().call_tool(validate_input=validate_input)

    def set_logging_level(self):
        """Register ``logging/setLevel`` (``docs/mcp/spec/schema-reference/logging-setlevel.md``)."""

        return super().set_logging_level()

    # ------------------------------------------------------------------
    # Transport helpers
    # ------------------------------------------------------------------

    async def serve_stdio(
        self,
        *,
        raise_exceptions: bool = False,
        stateless: bool = False,
    ) -> None:
        """Run the server over STDIO.

        STDIO transport is described in ``docs/mcp/spec/overview/messages.md``
        and commonly used for local tooling.  The helper configures the
        initialization options before delegating to ``Server.run``.
        """

        from mcp.server.stdio import stdio_server

        init_options = self.create_initialization_options()

        async with stdio_server() as (read_stream, write_stream):
            await self.run(
                read_stream,
                write_stream,
                init_options,
                raise_exceptions=raise_exceptions,
                stateless=stateless,
            )

    async def serve(
        self,
        *,
        transport: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Dispatch to a transport-specific serve helper.

        Args:
            transport: Optional transport name (currently only ``"stdio"``). If
                omitted, the default provided at construction time will be used.
            **kwargs: Additional keyword arguments forwarded to the underlying
                transport helper.
        """

        selected = (transport or self._default_transport)
        if selected is None:
            raise ValueError(
                "No transport specified. Provide one via 'transport' argument or"
                " when constructing MCPServer."
            )

        selected = selected.lower()
        if selected == "stdio":
            return await self.serve_stdio(**kwargs)
        if selected in {"http", "shttp", "streamable-http", "streamable_http"}:
            return await self.serve_streamable_http(**kwargs)

        raise ValueError(f"Unsupported transport '{selected}'.")

    async def serve_streamable_http(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 3000,
        json_response: bool = False,
        stateless: bool = False,
        allow_origins: Iterable[str] | None = ("*",),
        uvicorn_kwargs: dict[str, Any] | None = None,
    ) -> None:
        """Serve the MCP server over the Streamable HTTP transport."""
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
        from starlette.applications import Starlette
        from starlette.routing import Mount
        from starlette.types import Receive, Scope, Send

        session_manager = StreamableHTTPSessionManager(
            app=self,
            event_store=None,
            json_response=json_response,
            stateless=stateless,
        )

        async def handle(scope: Scope, receive: Receive, send: Send) -> None:
            await session_manager.handle_request(scope, receive, send)

        @asynccontextmanager
        async def lifespan(app: Starlette):
            async with session_manager.run():
                self._logger.info(
                    "Streamable HTTP transport running on http://%s:%s/mcp", host, port
                )
                yield

        starlette_app = Starlette(
            debug=False,
            routes=[Mount("/mcp", handle)],
            lifespan=lifespan,
        )

        if allow_origins:
            from starlette.middleware.cors import CORSMiddleware

            starlette_app = CORSMiddleware(
                starlette_app,
                allow_origins=list(allow_origins),
                allow_methods=["GET", "POST", "DELETE"],
                expose_headers=["Mcp-Session-Id"],
            )

        import uvicorn

        config = uvicorn.Config(
            app=starlette_app,
            host=host,
            port=port,
            log_level="info",
            **(uvicorn_kwargs or {}),
        )
        server = uvicorn.Server(config)
        await server.serve()


__all__ = ["NotificationFlags", "MCPServer"]
