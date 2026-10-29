"""Narrow optional MCP 2025-11-25 stdio bridge; no native writers or shell tools."""

from __future__ import annotations

import json
import sys
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from polyforge import __version__
from polyforge.capabilities.registry import catalog, validate_registry
from polyforge.contracts.validation import InputError, _reject_constant, _unique_object
from polyforge.knowledge.router import route_reference
from polyforge.security.paths import WorkspacePolicy
from polyforge.security.policy import redact

PROTOCOL = "2025-11-25"
LIMIT = 65536
TOOLS = [
    {
        "name": "polyforge_catalog",
        "description": "Read implemented capability descriptors; no execution",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "polyforge_reference_route",
        "description": "Select local DATA_ONLY references and a non-executing plan",
        "inputSchema": {
            "type": "object",
            "properties": {"request": {"type": "object"}},
            "required": ["request"],
            "additionalProperties": False,
        },
    },
    {
        "name": "polyforge_validate_descriptor",
        "description": "Validate a descriptor; validation never registers or executes it",
        "inputSchema": {
            "type": "object",
            "properties": {"descriptor": {"type": "object"}},
            "required": ["descriptor"],
            "additionalProperties": False,
        },
    },
]


def execute_readonly(policy: WorkspacePolicy, name: str, args: Any) -> dict[str, Any]:
    if not isinstance(args, dict):
        raise InputError("Tool arguments must be a bounded object")
    if name == "polyforge_catalog" and not args:
        return {"capabilities": catalog(), "execution_status": "NOT_RUN", "game_status": "PARTIAL"}
    if name == "polyforge_reference_route" and set(args) == {"request"}:
        return route_reference(policy, args["request"])
    if name == "polyforge_validate_descriptor" and set(args) == {"descriptor"}:
        validate_registry([args["descriptor"]])
        return {
            "validation": "PASS",
            "execution_status": "NOT_RUN",
            "registered": False,
            "game_status": "PARTIAL",
        }
    raise InputError("Unknown read-only tool or undeclared arguments")


def _id(value: Any) -> bool:
    return (
        type(value) is int
        and abs(value) <= 2**53 - 1
        or isinstance(value, str)
        and 1 <= len(value) <= 128
    )


class StdioServer:
    def __init__(self, policy: WorkspacePolicy, emit: Callable[[dict[str, Any]], Any]) -> None:
        self.policy, self.emit = policy, emit
        self.initialized = self.ready = self.closed = False
        self.guard = threading.RLock()
        self.active: dict[tuple[type, Any], threading.Event] = {}
        self.seen: set[tuple[type, Any]] = set()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="polyforge-readonly")

    def __enter__(self) -> StdioServer:
        return self

    def __exit__(self, *args: Any) -> None:
        # Finish bounded read-only calls already received before ordinary stdin EOF.
        self.pool.shutdown(wait=True)
        self.closed = True

    def _error(self, identifier: Any, code: int, message: str) -> None:
        self.emit(
            {
                "jsonrpc": "2.0",
                "id": identifier,
                "error": {"code": code, "message": redact(message)[:4096]},
            }
        )

    def _result(self, identifier: Any, value: dict[str, Any]) -> None:
        self.emit({"jsonrpc": "2.0", "id": identifier, "result": value})

    def _work(
        self,
        identifier: Any,
        key: tuple[type, Any],
        event: threading.Event,
        name: str,
        arguments: Any,
    ) -> None:
        try:
            if event.is_set():
                return
            result = execute_readonly(self.policy, name, arguments)
            response = {
                "content": [
                    {"type": "text", "text": json.dumps(result, ensure_ascii=True, allow_nan=False)}
                ],
                "isError": False,
            }
        except (InputError, OSError, ValueError, RecursionError) as exc:
            response = {
                "content": [{"type": "text", "text": redact(str(exc))[:4096]}],
                "isError": True,
            }
        finally:
            with self.guard:
                self.active.pop(key, None)
        with self.guard:
            if not event.is_set():
                self._result(identifier, response)

    def receive(self, value: Any) -> None:
        with self.guard:
            if self.closed:
                return
            if (
                not isinstance(value, dict)
                or set(value) - {"jsonrpc", "id", "method", "params"}
                or value.get("jsonrpc") != "2.0"
                or not isinstance(value.get("method"), str)
                or ("id" in value and not _id(value["id"]))
            ):
                self._error(None, -32600, "Invalid JSON-RPC request")
                return
            method, params = value["method"], value.get("params", {})
            if "id" not in value:
                if method == "notifications/initialized" and self.initialized and params == {}:
                    self.ready = True
                elif (
                    method == "notifications/cancelled"
                    and isinstance(params, dict)
                    and _id(params.get("requestId"))
                ):
                    key = (type(params["requestId"]), params["requestId"])
                    event = self.active.get(key)
                    if event is not None:
                        event.set()
                return
            identifier = value["id"]
            key = (type(identifier), identifier)
            if key in self.seen or len(self.seen) >= 4096:
                if key in self.active:
                    self.active[key].set()
                self._error(
                    identifier, -32600, "Duplicate request ID or session request budget exhausted"
                )
                return
            self.seen.add(key)
            if method == "ping" and params == {}:
                self._result(identifier, {})
                return
            if method == "initialize":
                if (
                    self.initialized
                    or not isinstance(params, dict)
                    or set(params) != {"protocolVersion", "capabilities", "clientInfo"}
                    or params["protocolVersion"] != PROTOCOL
                    or not isinstance(params["capabilities"], dict)
                    or not isinstance(params["clientInfo"], dict)
                    or not all(
                        isinstance(params["clientInfo"].get(k), str)
                        and 1 <= len(params["clientInfo"][k]) <= 256
                        for k in ("name", "version")
                    )
                ):
                    self._error(
                        identifier, -32602, "Invalid initialization or unsupported protocol version"
                    )
                    return
                self.initialized = True
                self._result(
                    identifier,
                    {
                        "protocolVersion": PROTOCOL,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "polyforge-readonly", "version": __version__},
                        "instructions": "DATA_ONLY bridge; client identity grants no authority.",
                    },
                )
                return
            if not self.ready:
                self._error(identifier, -32002, "Initialize and notify initialized before tool use")
                return
            if method == "tools/list" and params == {}:
                self._result(identifier, {"tools": TOOLS})
            elif (
                method == "tools/call"
                and isinstance(params, dict)
                and set(params) == {"name", "arguments"}
                and isinstance(params["name"], str)
            ):
                if params["name"] not in {t["name"] for t in TOOLS} or len(self.active) >= 8:
                    self._error(
                        identifier, -32602, "Unknown tool or pending-request budget exhausted"
                    )
                    return
                event = threading.Event()
                self.active[key] = event
                self.pool.submit(
                    self._work, identifier, key, event, params["name"], params["arguments"]
                )
            else:
                self._error(identifier, -32601, "Unsupported method or parameters")


def serve(workspace: str) -> int:
    policy = WorkspacePolicy(Path(workspace))
    writer = threading.Lock()

    def emit(value: dict[str, Any]) -> None:
        payload = json.dumps(value, ensure_ascii=True, allow_nan=False)
        with writer:
            sys.stdout.write(payload + "\n")
            sys.stdout.flush()

    with StdioServer(policy, emit) as server:
        while line := sys.stdin.buffer.readline(LIMIT + 1):
            if len(line) > LIMIT:
                emit(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32600,
                            "message": "Message exceeds 64 KiB; closing connection",
                        },
                    }
                )
                return 2
            try:
                message = json.loads(
                    line.decode("utf-8"),
                    object_pairs_hook=_unique_object,
                    parse_constant=_reject_constant,
                )
            except (ValueError, UnicodeError, RecursionError):
                emit(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": "Invalid bounded UTF-8 JSON"},
                    }
                )
                continue
            server.receive(message)
    return 0
