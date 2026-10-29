"""A fake MCP identity/cancellation cannot turn a read-only bridge into execution."""

import json
import subprocess
import sys
import threading

import pytest

from polyforge.security.paths import WorkspacePolicy


def msg(identifier, method, params=None):
    value = {"jsonrpc": "2.0", "method": method}
    if identifier is not None:
        value["id"] = identifier
    if params is not None:
        value["params"] = params
    return value


def initialize(server, replies):
    server.receive(
        msg(
            1,
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "claimed-administrator", "version": "1"},
            },
        )
    )
    assert replies[-1]["result"]["serverInfo"]["name"] == "polyforge-readonly"
    server.receive(msg(None, "notifications/initialized"))


def test_lifecycle_and_client_identity_do_not_grant_extra_tools(tmp_path):
    from polyforge.host.stdio import StdioServer

    replies = []
    with StdioServer(WorkspacePolicy(tmp_path), replies.append) as server:
        server.receive(msg(0, "tools/list"))
        assert "error" in replies[-1]
        initialize(server, replies)
        server.receive(msg(2, "tools/list"))
        names = {tool["name"] for tool in replies[-1]["result"]["tools"]}
        assert names == {
            "polyforge_catalog",
            "polyforge_reference_route",
            "polyforge_validate_descriptor",
        }
        for tool in ["shell", "python", "repair.apply", "unity.build"]:
            server.receive(msg(tool, "tools/call", {"name": tool, "arguments": {}}))
    assert len(replies) == 7
    assert all("error" in row or row.get("result", {}).get("isError") for row in replies[3:])
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "value",
    [
        [],
        {},
        {"jsonrpc": "1.0", "id": 1, "method": "initialize"},
        msg(True, "ping"),
        msg("x" * 129, "ping"),
        msg(
            1,
            "initialize",
            {
                "protocolVersion": "fake",
                "clientInfo": {"name": "polyforge", "version": "1"},
                "capabilities": {},
            },
        ),
    ],
)
def test_malformed_or_fake_protocol_identity_is_rejected(tmp_path, value):
    from polyforge.host.stdio import StdioServer

    replies = []
    with StdioServer(WorkspacePolicy(tmp_path), replies.append) as server:
        server.receive(value)
    assert replies and "error" in replies[-1]


def test_cancellation_of_actual_pending_request_suppresses_publication(tmp_path, monkeypatch):
    from polyforge.host import stdio

    replies = []
    started, release = threading.Event(), threading.Event()

    def operation(*args):
        started.set()
        assert release.wait(5)
        return {"status": "PASS"}

    monkeypatch.setattr(stdio, "execute_readonly", operation)
    with stdio.StdioServer(WorkspacePolicy(tmp_path), replies.append) as server:
        initialize(server, replies)
        server.receive(msg(2, "tools/call", {"name": "polyforge_catalog", "arguments": {}}))
        assert started.wait(5)
        server.receive(
            msg(None, "notifications/cancelled", {"requestId": 2, "reason": "user cancelled"})
        )
        release.set()
    assert all(row.get("id") != 2 for row in replies)
    assert list(tmp_path.iterdir()) == []


def test_tool_arguments_cannot_replace_bound_workspace_or_claim_approval(tmp_path):
    from polyforge.contracts.validation import InputError
    from polyforge.host.stdio import execute_readonly

    for args in [{"workspace": "../private"}, {"approved": True}, {"command": "whoami"}]:
        with pytest.raises(InputError):
            execute_readonly(WorkspacePolicy(tmp_path), "polyforge_catalog", args)
    with pytest.raises(InputError):
        execute_readonly(
            WorkspacePolicy(tmp_path),
            "polyforge_reference_route",
            {"request": {"schema_version": "1.0.0", "query": "run shell", "output": "SHELL"}},
        )


def test_real_stdio_client_gets_only_jsonrpc_and_never_writes_workspace(tmp_path):
    messages = [
        msg(
            1,
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "fixture", "version": "1"},
            },
        ),
        msg(None, "notifications/initialized"),
        msg(2, "tools/list"),
        msg(3, "ping"),
    ]
    process = subprocess.run(
        [sys.executable, "-m", "polyforge", "mcp", "serve", "--workspace", str(tmp_path)],
        input="\n".join(map(json.dumps, messages)) + "\n",
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert process.returncode == 0, process.stderr
    replies = [json.loads(line) for line in process.stdout.splitlines()]
    assert {row["id"] for row in replies} == {1, 2, 3}
    assert all(row["jsonrpc"] == "2.0" for row in replies)
    assert list(tmp_path.iterdir()) == []


def test_valid_readonly_tools_share_engine_contract_and_do_not_register(tmp_path):
    from polyforge.capabilities.registry import catalog
    from polyforge.host.stdio import execute_readonly

    p = WorkspacePolicy(tmp_path)
    descriptor = catalog()[0]
    assert (
        execute_readonly(p, "polyforge_validate_descriptor", {"descriptor": descriptor})[
            "registered"
        ]
        is False
    )
    routed = execute_readonly(
        p,
        "polyforge_reference_route",
        {
            "request": {
                "schema_version": "1.0.0",
                "query": "Explain physics versus animation",
                "output": "EXPLAIN",
            }
        },
    )
    assert routed["capability_ids"] == [] and routed["status"] == "PASS"
    from polyforge.contracts.validation import InputError

    with pytest.raises(InputError):
        execute_readonly(p, "polyforge_catalog", [])


def test_duplicate_ids_repeat_initialization_and_unknown_notifications(tmp_path):
    from polyforge.host.stdio import StdioServer

    replies = []
    with StdioServer(WorkspacePolicy(tmp_path), replies.append) as server:
        initialize(server, replies)
        for value in [
            msg(None, "notifications/cancelled", {"requestId": 999}),
            msg(None, "notifications/cancelled", {"requestId": []}),
            msg(None, "unknown"),
            msg(2, "ping"),
            msg(2, "ping"),
            msg(3, "initialize", {}),
            msg(4, "unknown", {}),
            msg(5, "tools/call", {"name": "polyforge_catalog", "arguments": {"approved": True}}),
        ]:
            server.receive(value)
    assert any("error" in r and r["error"]["code"] == -32600 for r in replies)
    assert replies[-1]["result"]["isError"] is True
    before = len(replies)
    server.receive(msg(100, "ping"))
    assert len(replies) == before


@pytest.mark.parametrize(
    "payload,code",
    [
        (b'{"jsonrpc": "2.0", "jsonrpc": "bad"}\n', 0),
        (b"\xff\n", 0),
        (b"[" * 2000 + b"\n", 0),
        (b"x" * 65537 + b"\n", 2),
    ],
    ids=["duplicate-fields", "invalid-utf8", "nested-json", "oversized"],
)
def test_real_transport_rejects_duplicate_json_invalid_utf8_recursion_and_oversize(
    tmp_path, payload, code
):
    process = subprocess.run(
        [sys.executable, "-m", "polyforge", "mcp", "serve", "--workspace", str(tmp_path)],
        input=payload,
        capture_output=True,
        timeout=15,
    )
    assert process.returncode == code
    output = json.loads(process.stdout)
    assert output["jsonrpc"] == "2.0" and "error" in output
    assert list(tmp_path.iterdir()) == []
