"""SDK-backed local stdio MCP server for the restricted campaign reader."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

from backend.agent.reader import AgentReadError, CampaignReader
from backend.agent.gateway_client import GatewayClient, REVIEW_TOOL_NAMES


def describe_profile(reader, gateway):
    data = reader.call("campaign_describe")
    if gateway:
        data["data"].update(
            {
                "tools": data["data"]["tools"] + list(REVIEW_TOOL_NAMES),
                "mutations_enabled": True,
                "operator_approval_required": True,
                "unavailable": [
                    "grant approval",
                    "publication",
                    "prep preview",
                    "shell",
                    "arbitrary files",
                ],
            }
        )
    return data


def build_server(reader: CampaignReader, gateway: GatewayClient | None = None):
    from mcp.server.lowlevel import Server
    from mcp.types import (
        CallToolResult,
        GetPromptResult,
        Prompt,
        PromptMessage,
        TextContent,
        Tool,
        ToolAnnotations,
    )

    instructions = (
        Path(__file__).resolve().parents[2]
        / ("agent/campaign-review-agent.md" if gateway else "agent/campaign-agent.md")
    ).read_text(encoding="utf-8")
    server = Server("DMA campaign reader", version="0.1.0", instructions=instructions)
    annotations = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    limit = {"type": "integer", "minimum": 1, "maximum": 50, "default": 20}
    source_id = {"type": "integer", "minimum": 1, "maximum": 2**63 - 1}
    optional_id = {"anyOf": [source_id, {"type": "null"}]}
    definitions = [
        (
            "campaign_describe",
            "Verify campaign binding, schema, role, epoch and capabilities.",
            {},
            [],
        ),
        (
            "campaign_read_entities",
            "Read accepted SQL entities with versioned source references.",
            {"entity_id": optional_id, "limit": limit},
            [],
        ),
        (
            "campaign_read_history",
            "Read approved, eligible GM session logs, excluding pending and rejected logs.",
            {"document_id": optional_id, "limit": limit},
            [],
        ),
        (
            "campaign_read_provenance",
            "Read reviewed candidate/source provenance for a SQL entity.",
            {"entity_id": source_id, "limit": limit},
            ["entity_id"],
        ),
        (
            "campaign_read_notes",
            "Read one exact overlay item with its file hash; no SQL/vault fallback.",
            {
                "note_type": {
                    "enum": ["campaign_overview", "session", "npc", "pc", "settlement"]
                },
                "item_id": {"type": "string", "minLength": 1, "maxLength": 128},
            },
            ["note_type", "item_id"],
        ),
        (
            "campaign_read_sessions",
            "Load explicit saved session associations for a fresh conversation.",
            {
                "session_id": {
                    "anyOf": [
                        {"type": "string", "minLength": 1, "maxLength": 128},
                        {"type": "null"},
                    ]
                },
                "limit": limit,
            },
            [],
        ),
        (
            "session_read_live",
            "Read operational live state and revision; this is not approved canon.",
            {},
            [],
        ),
        (
            "session_read_review",
            "Read pending review headers, or the explicitly selected draft/source.",
            {"draft_id": optional_id, "limit": limit},
            [],
        ),
    ]
    if gateway:
        text = {"type": "string", "minLength": 1, "maxLength": 128}
        receipt = {"approval_id": {"type": "string", "minLength": 36, "maxLength": 36}}
        stage = {
            "session_id": text,
            "request_key": text,
            "title": {"type": "string", "minLength": 1, "maxLength": 255},
            "content": {"type": "string", "minLength": 1, "maxLength": 100_000},
            "source_name": {"type": "string", "minLength": 1, "maxLength": 255},
            "source_refs": {
                "type": "array",
                "minItems": 1,
                "maxItems": 50,
                "items": {"type": "string", "minLength": 1, "maxLength": 2048},
            },
        }
        definitions.extend(
            [
                (
                    "session_stage_update",
                    "Request staging of an exact private source. Returns a PENDING operator approval receipt; no draft is saved until the operator approves and review_execute succeeds.",
                    stage,
                    list(stage),
                ),
                (
                    "review_propose",
                    "Request the operator's review of an exact candidate choice, promotion, or GM log decision. Cannot grant approval.",
                    {
                        "operation": {
                            "enum": ["decide_candidate", "promote", "finalize_log"]
                        },
                        "draft_id": source_id,
                        "expected_revision": source_id,
                        "session_id": text,
                        "candidate_id": text,
                        "decision": {
                            "enum": ["accepted", "rejected", "deferred", "approved"]
                        },
                        "reason": {"type": "string", "maxLength": 2000},
                    },
                    ["operation", "draft_id", "expected_revision", "session_id"],
                ),
                (
                    "review_receipt",
                    "Read one exact approval receipt and retained execution result.",
                    receipt,
                    ["approval_id"],
                ),
                (
                    "review_execute",
                    "Consume an already operator-approved receipt exactly once. No approval can be supplied or invented in arguments.",
                    receipt,
                    ["approval_id"],
                ),
            ]
        )

    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name=name,
                description=description,
                inputSchema={
                    "type": "object",
                    "properties": properties,
                    "required": required,
                    "additionalProperties": False,
                },
                annotations=(
                    annotations
                    if name not in REVIEW_TOOL_NAMES or name == "review_receipt"
                    else ToolAnnotations(
                        readOnlyHint=False,
                        destructiveHint=name == "review_execute",
                        idempotentHint=True,
                        openWorldHint=False,
                    )
                ),
            )
            for name, description, properties, required in definitions
        ]

    @server.call_tool(validate_input=True)
    async def call_tool(name: str, arguments: dict):
        try:
            data = (
                await gateway.call(name, arguments)
                if gateway and name in REVIEW_TOOL_NAMES
                else (
                    describe_profile(reader, gateway)
                    if name == "campaign_describe"
                    else reader.call(name, arguments)
                )
            )
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(data))],
                structuredContent=data,
            )
        except AgentReadError as exc:
            return CallToolResult(
                content=[TextContent(type="text", text=str(exc))], isError=True
            )

    @server.list_prompts()
    async def list_prompts():
        return [
            Prompt(
                name="campaign_resume",
                description="Resume the GM campaign from saved, source-qualified records.",
            )
        ]

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict | None = None):
        if name != "campaign_resume" or arguments:
            raise ValueError("Requested campaign prompt is unavailable")
        return GetPromptResult(
            messages=[
                PromptMessage(
                    role="user", content=TextContent(type="text", text=instructions)
                )
            ]
        )

    return server


async def serve(reader: CampaignReader, gateway: GatewayClient | None = None) -> None:
    from mcp.server.stdio import stdio_server

    if gateway:
        await gateway.health()
    server = build_server(reader, gateway)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument(
        "--operator-python",
        type=Path,
        help="Enable the guarded review profile against a generated fixture",
    )
    parser.add_argument(
        "--check", action="store_true", help="Verify binding without starting MCP"
    )
    args = parser.parse_args()
    try:
        reader = CampaignReader(args.binding)
        gateway = None
        if args.operator_python:
            from scripts.review_campaign_approval import fixture_binding

            fixture_binding(args.binding)
            gateway = GatewayClient(args.operator_python, args.binding)
        if args.check:
            if gateway:
                asyncio.run(gateway.health())
            print(json.dumps(describe_profile(reader, gateway), indent=2))
        else:
            asyncio.run(serve(reader, gateway))
    except AgentReadError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
