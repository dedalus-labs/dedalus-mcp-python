# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Base protocol message types."""

from mcp.types import (
    BaseMetadata,
    EmptyResult,
    ErrorData,
    Notification,
    NotificationParams,
    PaginatedRequest,
    PaginatedRequestParams,
    PaginatedResult,
    Request,
    RequestParams,
    Result,
    PARSE_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR,
    CONNECTION_CLOSED,
)

__all__ = [
    "BaseMetadata",
    "EmptyResult",
    "ErrorData",
    "Notification",
    "NotificationParams",
    "PaginatedRequest",
    "PaginatedRequestParams",
    "PaginatedResult",
    "Request",
    "RequestParams",
    "Result",
    "PARSE_ERROR",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "INVALID_PARAMS",
    "INTERNAL_ERROR",
    "CONNECTION_CLOSED",
]
