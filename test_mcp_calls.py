#!/usr/bin/env python3
"""Simulate MCP tool calls for testing."""

import httpx
import json

MCP_URL = "http://192.168.3.252:8500/mcp/"
TIMEOUT = 120.0


def send_mcp_request(session_id: str | None, method: str, params: dict, req_id: int) -> tuple[str | None, dict]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params,
    }

    try:
        response = httpx.post(MCP_URL, headers=headers, json=payload, timeout=TIMEOUT)
        new_session_id = response.headers.get("mcp-session-id", session_id)
        body = response.text

        if body:
            for line in body.strip().split("\n"):
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        return new_session_id, data
                    except json.JSONDecodeError:
                        pass
        return new_session_id, {}
    except Exception as e:
        print(f"Error: {e}")
        return session_id, {}


def main():
    # Step 1: Initialize
    print("\n" + "="*60)
    print("STEP 1: Initialize MCP Session")
    print("="*60)
    session_id, _ = send_mcp_request(None, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"},
    }, 1)
    print(f"✓ Session established: {session_id}")

    # Step 2: Send initialized notification
    send_mcp_request(session_id, "notifications/initialized", {}, 0)

    # TEST: Change password
    print("\n" + "="*60)
    print("TEST: playbook_admin_change_ssh_config - Change root password (SECOND TIME)")
    print("="*60)

    session_id, result = send_mcp_request(session_id, "tools/call", {
        "name": "playbook_admin_change_ssh_config",
        "arguments": {
            "targets": ["192.168.19.38"],
            "extravars": {
                "root_password": "1qaz@WSX"
            }
        }
    }, 100)

    if "result" in result:
        content = result["result"].get("content", [])
        if content and content[0].get("type") == "text":
            text = content[0].get("text", "")
            try:
                data = json.loads(text)
                task_id = data.get("task_id", "N/A")
                status = data.get("status", "N/A")
                summary = data.get("summary", {})

                print(f"Task ID: {task_id}")
                print(f"Status: {status}")
                print(f"Summary: {json.dumps(summary, indent=2)}")

                if status == "failed":
                    for host, host_result in data.get("results", {}).items():
                        rc = host_result.get("rc", -1)
                        stdout = host_result.get("stdout", "")[:1000]
                        stderr = host_result.get("stderr", "")[:500]
                        print(f"\nHost {host}:")
                        print(f"  rc={rc}")
                        print(f"  stdout: {stdout}")
                        print(f"  stderr: {stderr}")
            except json.JSONDecodeError:
                print(f"Raw output: {text[:500]}")
    else:
        print(f"Error response: {result}")

    print("\n" + "="*60)
    print("Test completed!")
    print("="*60)


if __name__ == "__main__":
    main()