# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Base protocol message types."""

from mcp.types import (
    CONNECTION_CLOSED,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
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
