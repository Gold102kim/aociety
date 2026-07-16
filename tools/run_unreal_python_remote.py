from __future__ import annotations

import argparse
import json
import os
import sys
import time


REMOTE_EXECUTION_PATH = r"E:\UE_5.8\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python"


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute a Python script in the open Aociety Unreal Editor.")
    parser.add_argument("script")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    script = os.path.abspath(args.script)
    if not os.path.exists(script):
        raise FileNotFoundError(script)

    sys.path.insert(0, REMOTE_EXECUTION_PATH)
    from remote_execution import MODE_EXEC_FILE, RemoteExecution

    remote = RemoteExecution()
    remote.start()
    try:
        deadline = time.time() + args.timeout
        nodes = []
        while time.time() < deadline:
            nodes = remote.remote_nodes
            if nodes:
                break
            time.sleep(0.25)
        if not nodes:
            raise RuntimeError("No Unreal Python remote execution nodes discovered")

        node = next(
            (n for n in nodes if "Aociety" in json.dumps(n, ensure_ascii=False)),
            nodes[0],
        )
        remote.open_command_connection(node["node_id"])
        command = (
            "import sys\n"
            f"sys.argv = [{script!r}]\n"
            f"__aociety_globals = {{'__name__': '__main__', '__file__': {script!r}}}\n"
            f"exec(compile(open({script!r}, encoding='utf-8').read(), {script!r}, 'exec'), __aociety_globals)\n"
        )
        result = remote.run_command(command, unattended=True, exec_mode=MODE_EXEC_FILE)
        print(json.dumps({"node": node, "result": result}, indent=2, ensure_ascii=False, default=str))
        return 0 if result.get("success") else 2
    finally:
        remote.stop()


if __name__ == "__main__":
    raise SystemExit(main())
