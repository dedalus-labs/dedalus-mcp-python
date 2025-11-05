# ==============================================================================
#                  © 2025 Dedalus Labs, Inc. and affiliates
#                            Licensed under MIT
#               github.com/dedalus-labs/openmcp-python/LICENSE
# ==============================================================================

"""MCP protocol type definitions.

Error code constants are promoted to module level for ergonomics.

Spec: https://modelcontextprotocol.io/specification/2025-06-18
"""

from __future__ import annotations

from mcp.types import (
    # Protocol constants & primitives
    LATEST_PROTOCOL_VERSION,
    DEFAULT_NEGOTIATED_VERSION,
    ProgressToken,
    Cursor,
    Role,
    RequestId,
    LoggingLevel,
    StopReason,
    IncludeContext,
    ElicitRequestedSchema,
    # Base classes
    BaseMetadata,
    RequestParams,
    PaginatedRequestParams,
    NotificationParams,
    Request,
    PaginatedRequest,
    Notification,
    Result,
    PaginatedResult,
    EmptyResult,
    # JSON-RPC infrastructure
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCNotification,
    JSONRPCError,
    JSONRPCMessage,
    # Error handling
    ErrorData,
    # Content types
    Annotations,
    TextContent,
    ImageContent,
    AudioContent,
    EmbeddedResource,
    ResourceLink,
    ContentBlock,
    TextResourceContents,
    BlobResourceContents,
    # Capability definitions
    Icon,
    Implementation,
    Tool,
    ToolAnnotations,
    Resource,
    ResourceTemplate,
    Prompt,
    PromptArgument,
    Root,
    # Capability configuration
    ServerCapabilities,
    ToolsCapability,
    ResourcesCapability,
    PromptsCapability,
    LoggingCapability,
    CompletionsCapability,
    ClientCapabilities,
    RootsCapability,
    SamplingCapability,
    ElicitationCapability,
    # Initialization
    InitializeRequest,
    InitializeRequestParams,
    InitializeResult,
    InitializedNotification,
    # Ping
    PingRequest,
    # Tools
    ListToolsRequest,
    ListToolsResult,
    CallToolRequest,
    CallToolRequestParams,
    CallToolResult,
    ToolListChangedNotification,
    # Prompts
    ListPromptsRequest,
    ListPromptsResult,
    GetPromptRequest,
    GetPromptRequestParams,
    GetPromptResult,
    PromptMessage,
    PromptListChangedNotification,
    # Resources
    ListResourcesRequest,
    ListResourcesResult,
    ListResourceTemplatesRequest,
    ListResourceTemplatesResult,
    ReadResourceRequest,
    ReadResourceRequestParams,
    ReadResourceResult,
    SubscribeRequest,
    SubscribeRequestParams,
    UnsubscribeRequest,
    UnsubscribeRequestParams,
    ResourceListChangedNotification,
    ResourceUpdatedNotification,
    ResourceUpdatedNotificationParams,
    # Completion
    CompleteRequest,
    CompleteRequestParams,
    CompleteResult,
    Completion,
    CompletionArgument,
    CompletionContext,
    ResourceTemplateReference,
    PromptReference,
    # Sampling
    CreateMessageRequest,
    CreateMessageRequestParams,
    CreateMessageResult,
    SamplingMessage,
    ModelPreferences,
    ModelHint,
    # Elicitation
    ElicitRequest,
    ElicitRequestParams,
    ElicitResult,
    # Roots
    ListRootsRequest,
    ListRootsResult,
    RootsListChangedNotification,
    # Logging
    SetLevelRequest,
    SetLevelRequestParams,
    LoggingMessageNotification,
    LoggingMessageNotificationParams,
    # Progress & cancellation
    ProgressNotification,
    ProgressNotificationParams,
    CancelledNotification,
    CancelledNotificationParams,
    # Union types (for protocol routing)
    ClientRequest,
    ClientNotification,
    ClientResult,
    ServerRequest,
    ServerNotification,
    ServerResult,
)

# Error code constants (module-level for convenience)
from mcp.types import (
    PARSE_ERROR,  # -32700
    INVALID_REQUEST,  # -32600
    METHOD_NOT_FOUND,  # -32601
    INVALID_PARAMS,  # -32602
    INTERNAL_ERROR,  # -32603
    CONNECTION_CLOSED,  # -32000
)

# Public API
__all__ = [
    # Protocol constants & primitives
    "LATEST_PROTOCOL_VERSION",
    "DEFAULT_NEGOTIATED_VERSION",
    "ProgressToken",
    "Cursor",
    "Role",
    "RequestId",
    "LoggingLevel",
    "StopReason",
    "IncludeContext",
    "ElicitRequestedSchema",
    # Error codes (most frequently used)
    "PARSE_ERROR",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "INVALID_PARAMS",
    "INTERNAL_ERROR",
    "CONNECTION_CLOSED",
    # Base classes
    "BaseMetadata",
    "RequestParams",
    "PaginatedRequestParams",
    "NotificationParams",
    "Request",
    "PaginatedRequest",
    "Notification",
    "Result",
    "PaginatedResult",
    "EmptyResult",
    # JSON-RPC infrastructure
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCNotification",
    "JSONRPCError",
    "JSONRPCMessage",
    # Error handling
    "ErrorData",
    # Content types
    "Annotations",
    "TextContent",
    "ImageContent",
    "AudioContent",
    "EmbeddedResource",
    "ResourceLink",
    "ContentBlock",
    "TextResourceContents",
    "BlobResourceContents",
    # Capability definitions
    "Icon",
    "Implementation",
    "Tool",
    "ToolAnnotations",
    "Resource",
    "ResourceTemplate",
    "Prompt",
    "PromptArgument",
    "Root",
    # Capability configuration
    "ServerCapabilities",
    "ToolsCapability",
    "ResourcesCapability",
    "PromptsCapability",
    "LoggingCapability",
    "CompletionsCapability",
    "ClientCapabilities",
    "RootsCapability",
    "SamplingCapability",
    "ElicitationCapability",
    # Initialization
    "InitializeRequest",
    "InitializeRequestParams",
    "InitializeResult",
    "InitializedNotification",
    # Ping
    "PingRequest",
    # Tools
    "ListToolsRequest",
    "ListToolsResult",
    "CallToolRequest",
    "CallToolRequestParams",
    "CallToolResult",
    "ToolListChangedNotification",
    # Prompts
    "ListPromptsRequest",
    "ListPromptsResult",
    "GetPromptRequest",
    "GetPromptRequestParams",
    "GetPromptResult",
    "PromptMessage",
    "PromptListChangedNotification",
    # Resources
    "ListResourcesRequest",
    "ListResourcesResult",
    "ListResourceTemplatesRequest",
    "ListResourceTemplatesResult",
    "ReadResourceRequest",
    "ReadResourceRequestParams",
    "ReadResourceResult",
    "SubscribeRequest",
    "SubscribeRequestParams",
    "UnsubscribeRequest",
    "UnsubscribeRequestParams",
    "ResourceListChangedNotification",
    "ResourceUpdatedNotification",
    "ResourceUpdatedNotificationParams",
    # Completion
    "CompleteRequest",
    "CompleteRequestParams",
    "CompleteResult",
    "Completion",
    "CompletionArgument",
    "CompletionContext",
    "ResourceTemplateReference",
    "PromptReference",
    # Sampling
    "CreateMessageRequest",
    "CreateMessageRequestParams",
    "CreateMessageResult",
    "SamplingMessage",
    "ModelPreferences",
    "ModelHint",
    # Elicitation
    "ElicitRequest",
    "ElicitRequestParams",
    "ElicitResult",
    # Roots
    "ListRootsRequest",
    "ListRootsResult",
    "RootsListChangedNotification",
    # Logging
    "SetLevelRequest",
    "SetLevelRequestParams",
    "LoggingMessageNotification",
    "LoggingMessageNotificationParams",
    # Progress & cancellation
    "ProgressNotification",
    "ProgressNotificationParams",
    "CancelledNotification",
    "CancelledNotificationParams",
    # Union types (for protocol routing)
    "ClientRequest",
    "ClientNotification",
    "ClientResult",
    "ServerRequest",
    "ServerNotification",
    "ServerResult",
]
