# Copyright (c) 2026 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Prompts — reusable message templates for LLMs.

Prompts are pre-defined message sequences that guide LLM behavior.
Clients fetch prompts and use them as conversation starters or
system instructions.

Usage:
    uv run python examples/capabilities/prompts/01_basic_prompts.py
"""

import asyncio
from datetime import datetime
import logging

from dedalus_mcp import MCPServer, prompt
from dedalus_mcp.types import PromptMessage, TextContent


for name in ("mcp", "httpx", "uvicorn"):
    logging.getLogger(name).setLevel(logging.WARNING)

server = MCPServer("prompts-demo")


# Simple prompt returning list of dicts
@prompt(name="code-review", description="System prompt for code review assistant")
def code_review_prompt(args: dict) -> list[dict]:
    language = args.get("language", "Python")
    return [
        {
            "role": "assistant",
            "content": f"""You are an expert {language} code reviewer. When reviewing code:
1. Check for bugs and logic errors
2. Suggest performance improvements
3. Ensure best practices are followed
4. Point out security concerns
5. Recommend better naming and structure

Be constructive and explain your reasoning.""",
        }
    ]


# Prompt with user context
@prompt(name="debug-helper", description="Help debug an error")
def debug_helper_prompt(args: dict) -> list[dict]:
    error = args.get("error", "Unknown error")
    context = args.get("context", "No additional context")

    return [
        {
            "role": "assistant",
            "content": """You are a debugging expert. Analyze errors systematically:
1. Identify the root cause
2. Explain why it happened
3. Provide a fix
4. Suggest how to prevent it in the future""",
        },
        {"role": "user", "content": f"I'm getting this error:\n\n```\n{error}\n```\n\nContext: {context}"},
    ]


# Multi-turn conversation starter
@prompt(name="interview-prep", description="Technical interview preparation")
def interview_prep_prompt(args: dict) -> list[dict]:
    topic = args.get("topic", "general programming")
    difficulty = args.get("difficulty", "medium")

    return [
        {
            "role": "assistant",
            "content": f"""You are a technical interviewer conducting a {difficulty}-level interview about {topic}.

Guidelines:
- Start with a warm-up question
- Progress to harder questions based on responses
- Ask follow-up questions to probe understanding
- Provide hints if the candidate is stuck
- Give constructive feedback after each answer""",
        },
        {"role": "user", "content": f"I'm ready to practice {topic} interview questions at {difficulty} level."},
        {"role": "assistant", "content": f"Great! Let's start with a warm-up question about {topic}..."},
    ]


# Using PromptMessage types directly
@prompt(name="sql-expert", description="SQL query optimization assistant")
def sql_expert_prompt(args: dict) -> list[PromptMessage]:
    dialect = args.get("dialect", "PostgreSQL")

    return [
        PromptMessage(
            role="assistant",
            content=TextContent(
                type="text",
                text=f"""You are a {dialect} expert. When helping with SQL:
- Write efficient, optimized queries
- Explain query execution plans
- Suggest proper indexing
- Follow {dialect}-specific best practices
- Consider data types and constraints""",
            ),
        )
    ]


# Dynamic prompt based on time
@prompt(name="daily-standup", description="Generate daily standup format")
def daily_standup_prompt(args: dict) -> list[dict]:
    team = args.get("team", "Engineering")
    today = datetime.now().strftime("%A, %B %d")

    return [
        {
            "role": "assistant",
            "content": f"""Today is {today}. You're facilitating the {team} team's daily standup.

Format for each team member:
1. What did you complete yesterday?
2. What are you working on today?
3. Any blockers or help needed?

Keep it concise. Flag blockers for immediate discussion.""",
        }
    ]


server.collect(code_review_prompt, debug_helper_prompt, interview_prep_prompt, sql_expert_prompt, daily_standup_prompt)

if __name__ == "__main__":
    print("Prompts server: http://127.0.0.1:8000/mcp")
    print("\nAvailable prompts:")
    print("  code-review     - Code review assistant")
    print("  debug-helper    - Error debugging helper")
    print("  interview-prep  - Technical interview practice")
    print("  sql-expert      - SQL optimization assistant")
    print("  daily-standup   - Standup meeting facilitator")
    print("\nPrompts accept arguments via prompts/get request")
    asyncio.run(server.serve())
