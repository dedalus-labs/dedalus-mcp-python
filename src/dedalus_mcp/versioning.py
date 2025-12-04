# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""MCP protocol versioning via typed capabilities and migrations."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, fields, is_dataclass, replace
from enum import Enum, auto
from functools import cache
from typing import Any, Callable


# --- Errors ------------------------------------------------------------------------


class UnsupportedProtocolVersionError(ValueError):
    """Requested protocol version is not supported."""

    def __init__(self, version: ProtocolVersion, supported: tuple[ProtocolVersion, ...]) -> None:
        self.version = version
        self.supported = supported
        super().__init__(f"Unsupported version {version}. Supported: {[str(v) for v in supported]}")


class UnknownFeatureError(KeyError):
    """Feature ID not found in any capability dataclass."""

    def __init__(self, feature: FeatureId) -> None:
        self.feature = feature
        super().__init__(f"No field tagged with {feature!r}")


class NoRequestContextError(RuntimeError):
    """Called version API outside of request context."""

    def __init__(self) -> None:
        super().__init__(
            "get_negotiated_version() called outside request context. "
            "Use ProtocolProfile.for_version() directly for startup/test code."
        )


class UninitializedSessionError(RuntimeError):
    """Session exists but initialization has not completed."""

    def __init__(self) -> None:
        super().__init__(
            "Protocol version not yet negotiated. Call get_negotiated_version() only after initialize completes."
        )


# --- Protocol Version --------------------------------------------------------------


@dataclass(order=True, frozen=True)
class ProtocolVersion:
    """Typed, ordered protocol version. ISO date format."""

    date: dt.date

    @classmethod
    def parse(cls, text: str) -> ProtocolVersion:
        return cls(dt.date.fromisoformat(text))

    def __str__(self) -> str:
        return self.date.isoformat()

    def __hash__(self) -> int:
        return hash(self.date)


V_2024_11_05 = ProtocolVersion.parse("2024-11-05")
V_2025_03_26 = ProtocolVersion.parse("2025-03-26")
V_2025_06_18 = ProtocolVersion.parse("2025-06-18")
V_2025_11_25 = ProtocolVersion.parse("2025-11-25")

ALL_VERSIONS: tuple[ProtocolVersion, ...] = (V_2024_11_05, V_2025_03_26, V_2025_06_18, V_2025_11_25)
SUPPORTED_VERSIONS: tuple[ProtocolVersion, ...] = ALL_VERSIONS
LATEST_VERSION: ProtocolVersion = V_2025_11_25


# --- Feature IDs -------------------------------------------------------------------


class FeatureId(Enum):
    """Closed set of trackable features. Type-safe, no string keys."""

    # 2025-03-26 additions
    PROGRESS_MESSAGE_FIELD = auto()
    JSONRPC_BATCHING = auto()
    TOOLS_ANNOTATIONS = auto()
    CONTENT_AUDIO = auto()
    COMPLETION_CAPABILITY_FLAG = auto()
    TRANSPORT_STREAMABLE_HTTP = auto()
    AUTH_OAUTH = auto()

    # 2025-06-18 additions
    TOOLS_STRUCTURED_OUTPUT = auto()
    TOOLS_RESOURCE_LINKS = auto()
    COMPLETION_CONTEXT_FIELD = auto()
    ELICITATION = auto()
    TRANSPORT_PROTOCOL_VERSION_HEADER = auto()
    SCHEMA_TITLE_FIELD = auto()
    SCHEMA_META_EXTENDED = auto()
    AUTH_RESOURCE_SERVER = auto()
    AUTH_RESOURCE_INDICATORS = auto()

    # 2025-11-25 additions
    AUTH_OIDC_DISCOVERY = auto()
    ICONS_METADATA = auto()
    AUTH_INCREMENTAL_SCOPE = auto()
    ELICITATION_URL_MODE = auto()
    SAMPLING_TOOL_CALLING = auto()
    AUTH_CLIENT_ID_METADATA = auto()
    TASKS_EXPERIMENTAL = auto()
    IMPLEMENTATION_DESCRIPTION = auto()
    SSE_POLLING = auto()
    ELICITATION_DEFAULT_VALUES = auto()


# --- Status Enums ------------------------------------------------------------------


class FieldStatus(Enum):
    """Lifecycle state of a schema field."""

    ABSENT = auto()
    OPTIONAL = auto()
    REQUIRED = auto()
    DEPRECATED = auto()


class BatchingState(Enum):
    """JSON-RPC batching support state."""

    UNSUPPORTED = auto()
    SUPPORTED = auto()
    REMOVED = auto()


class Availability(Enum):
    """Runtime availability for supports() queries."""

    UNAVAILABLE = auto()
    AVAILABLE = auto()
    DEPRECATED = auto()
    REMOVED = auto()


# --- feature_field helper ----------------------------------------------------------


def feature_field(feature: FeatureId, *, availability: dict[object, Availability] | None = None, **kwargs: Any) -> Any:
    """Dataclass field with feature metadata for availability mapping and drift detection."""
    md = dict(kwargs.pop("metadata", None) or {})
    md["feature"] = feature
    md["availability"] = availability
    return field(metadata=md, **kwargs)


# --- Capability Dataclasses --------------------------------------------------------


@dataclass(frozen=True)
class ProgressCaps:
    """Progress notification capabilities."""

    message_field: FieldStatus = feature_field(
        FeatureId.PROGRESS_MESSAGE_FIELD,
        default=FieldStatus.ABSENT,
        availability={
            FieldStatus.ABSENT: Availability.UNAVAILABLE,
            FieldStatus.OPTIONAL: Availability.AVAILABLE,
            FieldStatus.REQUIRED: Availability.AVAILABLE,
        },
    )


@dataclass(frozen=True)
class JsonRpcCaps:
    """JSON-RPC transport capabilities."""

    batching: BatchingState = feature_field(
        FeatureId.JSONRPC_BATCHING,
        default=BatchingState.UNSUPPORTED,
        availability={
            BatchingState.UNSUPPORTED: Availability.UNAVAILABLE,
            BatchingState.SUPPORTED: Availability.AVAILABLE,
            BatchingState.REMOVED: Availability.REMOVED,
        },
    )


@dataclass(frozen=True)
class ToolsCaps:
    """Tools capability flags."""

    annotations: FieldStatus = feature_field(
        FeatureId.TOOLS_ANNOTATIONS,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )
    structured_output: FieldStatus = feature_field(
        FeatureId.TOOLS_STRUCTURED_OUTPUT,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )
    resource_links: FieldStatus = feature_field(
        FeatureId.TOOLS_RESOURCE_LINKS,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )


@dataclass(frozen=True)
class ContentCaps:
    """Content type support."""

    audio: FieldStatus = feature_field(
        FeatureId.CONTENT_AUDIO,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )


@dataclass(frozen=True)
class CompletionCaps:
    """Completion capability flags."""

    capability_flag: FieldStatus = feature_field(
        FeatureId.COMPLETION_CAPABILITY_FLAG,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )
    context_field: FieldStatus = feature_field(
        FeatureId.COMPLETION_CONTEXT_FIELD,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )


@dataclass(frozen=True)
class ElicitationCaps:
    """Elicitation capability."""

    supported: FieldStatus = feature_field(
        FeatureId.ELICITATION,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )
    url_mode: FieldStatus = feature_field(
        FeatureId.ELICITATION_URL_MODE,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )
    default_values: FieldStatus = feature_field(
        FeatureId.ELICITATION_DEFAULT_VALUES,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )


@dataclass(frozen=True)
class TransportCaps:
    """Transport-level capabilities."""

    protocol_version_header: FieldStatus = feature_field(
        FeatureId.TRANSPORT_PROTOCOL_VERSION_HEADER,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.REQUIRED: Availability.AVAILABLE},
    )
    streamable_http: FieldStatus = feature_field(
        FeatureId.TRANSPORT_STREAMABLE_HTTP,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )
    sse_polling: FieldStatus = feature_field(
        FeatureId.SSE_POLLING,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )


@dataclass(frozen=True)
class SchemaCaps:
    """Schema-level features."""

    title_field: FieldStatus = feature_field(
        FeatureId.SCHEMA_TITLE_FIELD,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )
    meta_extended: FieldStatus = feature_field(
        FeatureId.SCHEMA_META_EXTENDED,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )
    icons_metadata: FieldStatus = feature_field(
        FeatureId.ICONS_METADATA,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )


@dataclass(frozen=True)
class AuthCaps:
    """Authorization capabilities."""

    oauth: FieldStatus = feature_field(
        FeatureId.AUTH_OAUTH,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )
    resource_server: FieldStatus = feature_field(
        FeatureId.AUTH_RESOURCE_SERVER,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )
    resource_indicators: FieldStatus = feature_field(
        FeatureId.AUTH_RESOURCE_INDICATORS,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )
    oidc_discovery: FieldStatus = feature_field(
        FeatureId.AUTH_OIDC_DISCOVERY,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )
    incremental_scope: FieldStatus = feature_field(
        FeatureId.AUTH_INCREMENTAL_SCOPE,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )
    client_id_metadata: FieldStatus = feature_field(
        FeatureId.AUTH_CLIENT_ID_METADATA,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )


@dataclass(frozen=True)
class SamplingCaps:
    """Sampling capability flags."""

    tool_calling: FieldStatus = feature_field(
        FeatureId.SAMPLING_TOOL_CALLING,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )


@dataclass(frozen=True)
class TasksCaps:
    """Tasks capability (experimental)."""

    experimental: FieldStatus = feature_field(
        FeatureId.TASKS_EXPERIMENTAL,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )


@dataclass(frozen=True)
class ImplementationCaps:
    """Implementation metadata fields."""

    description_field: FieldStatus = feature_field(
        FeatureId.IMPLEMENTATION_DESCRIPTION,
        default=FieldStatus.ABSENT,
        availability={FieldStatus.ABSENT: Availability.UNAVAILABLE, FieldStatus.OPTIONAL: Availability.AVAILABLE},
    )


@dataclass(frozen=True)
class ProtocolCaps:
    """Complete capabilities for a protocol version."""

    version: ProtocolVersion
    progress: ProgressCaps = field(default_factory=ProgressCaps)
    jsonrpc: JsonRpcCaps = field(default_factory=JsonRpcCaps)
    tools: ToolsCaps = field(default_factory=ToolsCaps)
    content: ContentCaps = field(default_factory=ContentCaps)
    completion: CompletionCaps = field(default_factory=CompletionCaps)
    elicitation: ElicitationCaps = field(default_factory=ElicitationCaps)
    transport: TransportCaps = field(default_factory=TransportCaps)
    schema: SchemaCaps = field(default_factory=SchemaCaps)
    auth: AuthCaps = field(default_factory=AuthCaps)
    sampling: SamplingCaps = field(default_factory=SamplingCaps)
    tasks: TasksCaps = field(default_factory=TasksCaps)
    implementation: ImplementationCaps = field(default_factory=ImplementationCaps)


# --- Migrations --------------------------------------------------------------------


class ChangeKind(Enum):
    """Type of spec change for documentation."""

    FIELD_ADDED = auto()
    FIELD_REMOVED = auto()
    FEATURE_ADDED = auto()
    FEATURE_REMOVED = auto()
    NORMATIVE_TIGHTENING = auto()
    SEMANTIC_CHANGE = auto()
    DEPRECATION = auto()


@dataclass(frozen=True)
class SpecChange:
    """Documents a single change in the spec."""

    feature: FeatureId
    kind: ChangeKind
    note: str
    pr: str | None = None


@dataclass(frozen=True)
class Migration:
    """Transforms capabilities from previous version."""

    version: ProtocolVersion
    apply: Callable[[ProtocolCaps], ProtocolCaps]
    changes: tuple[SpecChange, ...]


# --- Baseline and Migrations -------------------------------------------------------

BASE_CAPS = ProtocolCaps(version=V_2024_11_05)


def _upgrade_2025_03_26(prev: ProtocolCaps) -> ProtocolCaps:
    return replace(
        prev,
        progress=replace(prev.progress, message_field=FieldStatus.OPTIONAL),
        jsonrpc=replace(prev.jsonrpc, batching=BatchingState.SUPPORTED),
        tools=replace(prev.tools, annotations=FieldStatus.OPTIONAL),
        content=replace(prev.content, audio=FieldStatus.OPTIONAL),
        completion=replace(prev.completion, capability_flag=FieldStatus.OPTIONAL),
        transport=replace(prev.transport, streamable_http=FieldStatus.OPTIONAL),
        auth=replace(prev.auth, oauth=FieldStatus.OPTIONAL),
    )


def _upgrade_2025_06_18(prev: ProtocolCaps) -> ProtocolCaps:
    return replace(
        prev,
        jsonrpc=replace(prev.jsonrpc, batching=BatchingState.REMOVED),
        tools=replace(prev.tools, structured_output=FieldStatus.OPTIONAL, resource_links=FieldStatus.OPTIONAL),
        completion=replace(prev.completion, context_field=FieldStatus.OPTIONAL),
        elicitation=replace(prev.elicitation, supported=FieldStatus.OPTIONAL),
        transport=replace(prev.transport, protocol_version_header=FieldStatus.REQUIRED),
        schema=replace(prev.schema, title_field=FieldStatus.OPTIONAL, meta_extended=FieldStatus.OPTIONAL),
        auth=replace(prev.auth, resource_server=FieldStatus.OPTIONAL, resource_indicators=FieldStatus.OPTIONAL),
    )


def _upgrade_2025_11_25(prev: ProtocolCaps) -> ProtocolCaps:
    return replace(
        prev,
        auth=replace(
            prev.auth,
            oidc_discovery=FieldStatus.OPTIONAL,
            incremental_scope=FieldStatus.OPTIONAL,
            client_id_metadata=FieldStatus.OPTIONAL,
        ),
        schema=replace(prev.schema, icons_metadata=FieldStatus.OPTIONAL),
        elicitation=replace(prev.elicitation, url_mode=FieldStatus.OPTIONAL, default_values=FieldStatus.OPTIONAL),
        sampling=replace(prev.sampling, tool_calling=FieldStatus.OPTIONAL),
        tasks=replace(prev.tasks, experimental=FieldStatus.OPTIONAL),
        transport=replace(prev.transport, sse_polling=FieldStatus.OPTIONAL),
        implementation=replace(prev.implementation, description_field=FieldStatus.OPTIONAL),
    )


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=V_2025_03_26,
        apply=_upgrade_2025_03_26,
        changes=(
            SpecChange(FeatureId.PROGRESS_MESSAGE_FIELD, ChangeKind.FIELD_ADDED, "Optional message field"),
            SpecChange(FeatureId.JSONRPC_BATCHING, ChangeKind.FEATURE_ADDED, "Batching allowed", pr="#228"),
            SpecChange(FeatureId.TOOLS_ANNOTATIONS, ChangeKind.FIELD_ADDED, "readOnly, destructive", pr="#185"),
            SpecChange(FeatureId.CONTENT_AUDIO, ChangeKind.FEATURE_ADDED, "Audio content type"),
            SpecChange(FeatureId.COMPLETION_CAPABILITY_FLAG, ChangeKind.FEATURE_ADDED, "Explicit capability"),
            SpecChange(FeatureId.TRANSPORT_STREAMABLE_HTTP, ChangeKind.FEATURE_ADDED, "Replaces HTTP+SSE", pr="#206"),
            SpecChange(FeatureId.AUTH_OAUTH, ChangeKind.FEATURE_ADDED, "OAuth 2.1 framework", pr="#133"),
        ),
    ),
    Migration(
        version=V_2025_06_18,
        apply=_upgrade_2025_06_18,
        changes=(
            SpecChange(FeatureId.JSONRPC_BATCHING, ChangeKind.FEATURE_REMOVED, "Batching removed", pr="#416"),
            SpecChange(FeatureId.TOOLS_STRUCTURED_OUTPUT, ChangeKind.FIELD_ADDED, "outputSchema", pr="#371"),
            SpecChange(FeatureId.TOOLS_RESOURCE_LINKS, ChangeKind.FIELD_ADDED, "Resource links in results", pr="#603"),
            SpecChange(FeatureId.COMPLETION_CONTEXT_FIELD, ChangeKind.FIELD_ADDED, "Context in request", pr="#598"),
            SpecChange(FeatureId.ELICITATION, ChangeKind.FEATURE_ADDED, "Server requests user input", pr="#382"),
            SpecChange(
                FeatureId.TRANSPORT_PROTOCOL_VERSION_HEADER, ChangeKind.FIELD_ADDED, "Required header", pr="#548"
            ),
            SpecChange(FeatureId.SCHEMA_TITLE_FIELD, ChangeKind.FIELD_ADDED, "Human-friendly names", pr="#663"),
            SpecChange(FeatureId.SCHEMA_META_EXTENDED, ChangeKind.FIELD_ADDED, "Extended to more types", pr="#710"),
            SpecChange(FeatureId.AUTH_RESOURCE_SERVER, ChangeKind.FEATURE_ADDED, "OAuth Resource Server", pr="#338"),
            SpecChange(FeatureId.AUTH_RESOURCE_INDICATORS, ChangeKind.FEATURE_ADDED, "RFC 8707", pr="#734"),
        ),
    ),
    Migration(
        version=V_2025_11_25,
        apply=_upgrade_2025_11_25,
        changes=(
            SpecChange(FeatureId.AUTH_OIDC_DISCOVERY, ChangeKind.FEATURE_ADDED, "OpenID Connect Discovery", pr="#797"),
            SpecChange(
                FeatureId.ICONS_METADATA, ChangeKind.FIELD_ADDED, "Icons for tools/resources/prompts", pr="SEP-973"
            ),
            SpecChange(
                FeatureId.AUTH_INCREMENTAL_SCOPE,
                ChangeKind.FEATURE_ADDED,
                "WWW-Authenticate scope consent",
                pr="SEP-835",
            ),
            SpecChange(FeatureId.ELICITATION_URL_MODE, ChangeKind.FEATURE_ADDED, "URL elicitation mode", pr="SEP-1036"),
            SpecChange(
                FeatureId.SAMPLING_TOOL_CALLING, ChangeKind.FIELD_ADDED, "tools/toolChoice in sampling", pr="SEP-1577"
            ),
            SpecChange(
                FeatureId.AUTH_CLIENT_ID_METADATA, ChangeKind.FEATURE_ADDED, "OAuth Client ID Metadata", pr="SEP-991"
            ),
            SpecChange(
                FeatureId.TASKS_EXPERIMENTAL, ChangeKind.FEATURE_ADDED, "Experimental tasks support", pr="SEP-1686"
            ),
            SpecChange(
                FeatureId.IMPLEMENTATION_DESCRIPTION, ChangeKind.FIELD_ADDED, "description in Implementation", pr=None
            ),
            SpecChange(FeatureId.SSE_POLLING, ChangeKind.FEATURE_ADDED, "SSE polling support", pr="SEP-1699"),
            SpecChange(
                FeatureId.ELICITATION_DEFAULT_VALUES, ChangeKind.FIELD_ADDED, "Default values in schemas", pr="SEP-1034"
            ),
        ),
    ),
)


# --- capabilities_for --------------------------------------------------------------


@cache
def capabilities_for(version: ProtocolVersion) -> ProtocolCaps:
    """Build capabilities for a version. Cached. Raises on unsupported versions."""
    if version not in SUPPORTED_VERSIONS:
        raise UnsupportedProtocolVersionError(version, SUPPORTED_VERSIONS)

    caps = BASE_CAPS
    for migration in MIGRATIONS:
        if migration.version <= version:
            caps = migration.apply(caps)
    return replace(caps, version=version)


# --- Feature State Lookup ----------------------------------------------------------


def _feature_state(caps: ProtocolCaps, feature: FeatureId) -> Availability:
    """Walk capability tree, find field tagged with feature, return availability."""

    def visit(obj: object, typ: type) -> Availability | None:
        for f in fields(typ):  # type: ignore[arg-type]
            value = getattr(obj, f.name)
            md = f.metadata
            if md.get("feature") is feature:
                mapping: dict[object, Availability] | None = md.get("availability")
                if mapping is None:
                    return Availability.AVAILABLE if value else Availability.UNAVAILABLE
                if value not in mapping:
                    raise KeyError(f"Value {value!r} not in availability map for {feature!r}")
                return mapping[value]
            if is_dataclass(value):
                found = visit(value, type(value))
                if found is not None:
                    return found
        return None

    result = visit(caps, type(caps))
    if result is None:
        raise UnknownFeatureError(feature)
    return result


# --- ProtocolProfile ---------------------------------------------------------------


class ProtocolProfile:
    """Runtime interface for version-specific behavior."""

    def __init__(self, caps: ProtocolCaps) -> None:
        self.caps = caps

    @property
    def version(self) -> ProtocolVersion:
        return self.caps.version

    def supports(self, feature: FeatureId) -> bool:
        """True if feature is available or deprecated (still usable)."""
        state = _feature_state(self.caps, feature)
        return state in (Availability.AVAILABLE, Availability.DEPRECATED)

    def feature_state(self, feature: FeatureId) -> Availability:
        """Full availability state for a feature."""
        return _feature_state(self.caps, feature)

    @classmethod
    def for_version(cls, version: ProtocolVersion) -> ProtocolProfile:
        return cls(capabilities_for(version))


# --- Drift Detection (for tests) ---------------------------------------------------


def features_changed(before: ProtocolCaps, after: ProtocolCaps) -> set[FeatureId]:
    """Return features whose fields differ between two caps. Used in tests."""
    changed: set[FeatureId] = set()

    def walk(b: object, a: object, typ: type) -> None:
        for f in fields(typ):  # type: ignore[arg-type]
            vb, va = getattr(b, f.name), getattr(a, f.name)
            feature: FeatureId | None = f.metadata.get("feature")
            if feature is not None:
                if vb != va:
                    changed.add(feature)
            elif is_dataclass(vb):
                walk(vb, va, type(vb))

    walk(before, after, type(before))
    return changed


# --- Negotiated Version Helper -----------------------------------------------------


def get_negotiated_version() -> ProtocolVersion:
    """Return the negotiated version from request context.

    Raises:
        NoRequestContextError: Called outside MCP request handler.
        UninitializedSessionError: Session exists but initialize not complete.
        UnsupportedProtocolVersionError: Client requested unsupported version.
    """
    from mcp.server.lowlevel.server import request_ctx

    try:
        ctx = request_ctx.get()
    except LookupError as e:
        raise NoRequestContextError from e

    session = ctx.session
    client_params = getattr(session, "client_params", None)
    if client_params is None:
        raise UninitializedSessionError

    requested = getattr(client_params, "protocolVersion", None)
    if requested is None:
        raise UninitializedSessionError

    pv = ProtocolVersion.parse(str(requested))
    if pv not in SUPPORTED_VERSIONS:
        raise UnsupportedProtocolVersionError(pv, SUPPORTED_VERSIONS)

    return pv


def current_profile() -> ProtocolProfile:
    """Get ProtocolProfile for the current request context.

    Raises same errors as get_negotiated_version().
    """
    return ProtocolProfile.for_version(get_negotiated_version())


# --- Exports -----------------------------------------------------------------------

__all__ = [
    # Version
    "ProtocolVersion",
    "V_2024_11_05",
    "V_2025_03_26",
    "V_2025_06_18",
    "V_2025_11_25",
    "ALL_VERSIONS",
    "SUPPORTED_VERSIONS",
    "LATEST_VERSION",
    # Features
    "FeatureId",
    "FieldStatus",
    "BatchingState",
    "Availability",
    # Capabilities
    "ProtocolCaps",
    "ProgressCaps",
    "JsonRpcCaps",
    "ToolsCaps",
    "ContentCaps",
    "CompletionCaps",
    "ElicitationCaps",
    "TransportCaps",
    "SchemaCaps",
    "AuthCaps",
    "SamplingCaps",
    "TasksCaps",
    "ImplementationCaps",
    # Migrations
    "Migration",
    "SpecChange",
    "ChangeKind",
    "MIGRATIONS",
    "BASE_CAPS",
    # Runtime
    "capabilities_for",
    "ProtocolProfile",
    "get_negotiated_version",
    "current_profile",
    # Testing
    "features_changed",
    # Errors
    "UnsupportedProtocolVersionError",
    "UnknownFeatureError",
    "NoRequestContextError",
    "UninitializedSessionError",
]
