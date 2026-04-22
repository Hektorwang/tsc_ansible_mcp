#!/usr/bin/env python3
"""Test MCP server tool list functionality."""

import httpx
import json
import sys

MCP_URL = "http://192.168.3.252:8500/mcp/"

def main():
    client = httpx.Client()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    
    # Step 1: Initialize
    print("Step 1: Sending initialize request...")
    init_response = client.post(
        MCP_URL,
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0.0"},
            },
        },
    )
    
    print(f"  Status: {init_response.status_code}")
    print(f"  Headers: {dict(init_response.headers)}")
    
    session_id = init_response.headers.get("mcp-session-id")
    if not session_id:
        print("ERROR: No session ID in response!")
        sys.exit(1)
    
    print(f"  Session ID: {session_id}")
    
    headers["Mcp-Session-Id"] = session_id
    
    # Step 2: Send initialized notification
    print("\nStep 2: Sending initialized notification...")
    notif_response = client.post(
        MCP_URL,
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        },
    )
    print(f"  Status: {notif_response.status_code}")
    
    # Step 3: Request tools list
    print("\nStep 3: Requesting tools/list...")
    tools_response = client.post(
        MCP_URL,
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
    )
    
    print(f"  Status: {tools_response.status_code}")
    print(f"  Content-Type: {tools_response.headers.get('content-type')}")
    print(f"  Response body:\n{tools_response.text}")
    
    # Parse response
    if "event:" in tools_response.text:
        # SSE format
        for line in tools_response.text.split("\n"):
            if line.startswith("data:"):
                data = json.loads(line[5:].strip())
                if "result" in data and "tools" in data["result"]:
                    tools = data["result"]["tools"]
                    print(f"\n=== TOOL LIST ({len(tools)} tools) ===")
                    for tool in tools:
                        print(f"  - {tool.get('name', 'unknown')}")
                break
    else:
        # JSON format
        try:
            data = tools_response.json()
            if "result" in data and "tools" in data["result"]:
                tools = data["result"]["tools"]
                print(f"\n=== TOOL LIST ({len(tools)} tools) ===")
                for tool in tools:
                    print(f"  - {tool.get('name', 'unknown')}")
            else:
                print(f"  Error: {data}")
        except:
            print(f"  Failed to parse JSON response")

if __name__ == "__main__":
    main()
