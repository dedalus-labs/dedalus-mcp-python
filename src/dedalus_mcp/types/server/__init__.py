# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Server capability types."""

from .completions import *
from .logging import *
from .prompts import *
from .resources import *
from .tools import *

__all__ = [
    # Tools
    "Tool",
    "ListToolsRequest",
    "ListToolsResult",
    "CallToolRequest",
    "CallToolRequestParams",
    "CallToolResult",
    "ToolListChangedNotification",
    # Resources
    "Resource",
    "ResourceTemplate",
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
    # Prompts
    "Prompt",
    "PromptArgument",
    "PromptMessage",
    "PromptReference",
    "ListPromptsRequest",
    "ListPromptsResult",
    "GetPromptRequest",
    "GetPromptRequestParams",
    "GetPromptResult",
    "PromptListChangedNotification",
    # Completions
    "CompleteRequest",
    "CompleteRequestParams",
    "CompleteResult",
    "Completion",
    "CompletionArgument",
    "CompletionContext",
    "ResourceTemplateReference",
    # Logging
    "SetLevelRequest",
    "SetLevelRequestParams",
    "LoggingMessageNotification",
    "LoggingMessageNotificationParams",
]
