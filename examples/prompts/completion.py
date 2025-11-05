# ==============================================================================
#                  © 2025 Dedalus Labs, Inc. and affiliates
#                            Licensed under MIT
#               github.com/dedalus-labs/openmcp-python/LICENSE
# ==============================================================================

"""Prompt argument completion for enhanced client UX.

Demonstrates autocomplete support for prompt parameters using the completion
capability. Completion handlers provide dynamic suggestions based on partial
input and existing argument context, enabling type-ahead and validation.

Pattern:
- @completion(prompt="name") links completer to prompt
- Completion functions receive CompletionArgument (name, partial value)
- CompletionContext provides already-set arguments for dependent completions
- Return list[str] of matching suggestions

When to use:
- Large argument spaces (languages, frameworks, regions)
- Dependent completions (framework depends on language)
- Client-side validation and suggestion
- Enhanced argument discovery and UX

Spec: https://modelcontextprotocol.io/specification/2025-06-18/server/completion
Reference: docs/mcp/spec/schema-reference/completion-complete.md
Usage: uv run python examples/prompts/completion.py
"""

from __future__ import annotations

import asyncio
import logging

from openmcp import MCPServer, completion, prompt
from openmcp.types import CompletionArgument, CompletionContext

# Suppress logs for clean demo output
for logger_name in ("mcp", "httpx", "uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

# Static knowledge base for completion
LANGUAGES = ["python", "javascript", "typescript", "rust", "go"]
FRAMEWORKS = {
    "python": ["django", "flask", "fastapi"],
    "javascript": ["react", "vue", "angular"],
    "typescript": ["next.js", "nest.js"],
}

server = MCPServer("prompt-completion")

with server.binding():

    @prompt(
        name="scaffold-project",
        description="Generate project structure for a new application",
        arguments=[
            {"name": "language", "description": "Programming language", "required": True},
            {"name": "framework", "description": "Framework", "required": False},
        ],
    )
    def scaffold_prompt(arguments: dict[str, str] | None) -> list[dict[str, str]]:
        """Render project scaffold instructions."""
        if not arguments:
            raise ValueError("Arguments required")

        lang = arguments["language"]
        framework = arguments.get("framework", "none")

        return [
            {"role": "assistant", "content": f"You are a {lang} expert."},
            {
                "role": "user",
                "content": f"Create a {lang} project" + (f" using {framework}" if framework != "none" else ""),
            },
        ]

    @completion(prompt="scaffold-project")
    def complete_scaffold_args(
        argument: CompletionArgument,
        context: CompletionContext | None,
    ) -> list[str]:
        """Provide autocomplete suggestions for language/framework.

        argument.name: parameter being completed
        argument.value: partial text typed so far
        context: already-provided arguments (for dependent completions)
        """
        partial = argument.value.lower() if argument.value else ""

        if argument.name == "language":
            return [lang for lang in LANGUAGES if lang.startswith(partial)]

        if argument.name == "framework" and context:
            lang = context.dict().get("language")
            if lang in FRAMEWORKS:
                return [fw for fw in FRAMEWORKS[lang] if fw.startswith(partial)]

        return []


async def main() -> None:
    await server.serve(
        transport="streamable-http",
        verbose=False,
        log_level="critical",
        uvicorn_options={"access_log": False},
    )


if __name__ == "__main__":
    asyncio.run(main())
