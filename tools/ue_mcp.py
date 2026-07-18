import argparse
import base64
import http.client
import json
from pathlib import Path


MCP_URL = "http://127.0.0.1:8181/mcp"


def post(payload, session_id=None):
    connection = http.client.HTTPConnection("127.0.0.1", 8181, timeout=120)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    connection.request("POST", "/mcp", body=json.dumps(payload).encode("utf-8"), headers=headers)
    response = connection.getresponse()
    new_session_id = response.getheader("Mcp-Session-Id") or session_id
    content_type = response.getheader("Content-Type")
    try:
        if content_type and content_type.startswith("text/event-stream"):
            expected_id = payload.get("id")
            result = None
            while True:
                line = response.readline()
                if not line:
                    break
                if not line.startswith(b"data:"):
                    continue
                event = json.loads(line[5:].strip().decode("utf-8"))
                if expected_id is None or event.get("id") == expected_id:
                    result = event
                    break
        else:
            raw = response.read()
            result = json.loads(raw) if raw else None
        return new_session_id, {
            "status": response.status,
            "content_type": content_type,
            "body": result,
        }
    finally:
        connection.close()


def initialize():
    session_id, result = post(
        {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "codex", "version": "1.0"},
            },
            "id": 1,
        }
    )
    post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, session_id)
    return session_id, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("list", "describe", "call"))
    parser.add_argument("--toolset")
    parser.add_argument("--tool")
    parser.add_argument("--arguments", default="{}")
    parser.add_argument("--arguments-file")
    parser.add_argument("--output")
    args = parser.parse_args()

    session_id, init_result = initialize()
    if args.command == "list":
        name = "list_toolsets"
        arguments = {}
    elif args.command == "describe":
        name = "describe_toolset"
        arguments = {"toolset_name": args.toolset}
    else:
        name = "call_tool"
        tool_arguments = (
            json.loads(Path(args.arguments_file).read_text(encoding="utf-8"))
            if args.arguments_file
            else json.loads(args.arguments)
        )
        arguments = {
            "toolset_name": args.toolset,
            "tool_name": args.tool,
            "arguments": tool_arguments,
        }

    _, result = post(
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
            "id": 2,
        },
        session_id,
    )
    if args.output:
        outer = result["body"]["result"]["content"][0]["text"]
        inner = json.loads(outer)
        return_value = inner["returnValue"]
        image_value = return_value.get("image", return_value)
        Path(args.output).write_bytes(base64.b64decode(image_value["data"]))
        print(json.dumps({
            "output": args.output,
            "mime_type": image_value.get("mimeType"),
            "width": image_value.get("width"),
            "height": image_value.get("height"),
            "camera_location": return_value.get("cameraLocation"),
            "camera_rotation": return_value.get("cameraRotation"),
            "field_of_view": return_value.get("fieldOfView", return_value.get("cameraFOV")),
        }, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"initialize": init_result, "result": result}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
