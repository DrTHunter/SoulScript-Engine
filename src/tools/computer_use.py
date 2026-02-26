"""Computer Use tool — executes Anthropic Computer Use actions in a sandbox.

This tool handles three Anthropic Computer Use action types:
  1. **computer** — screenshot, mouse, keyboard actions
  2. **bash**     — execute shell commands
  3. **str_replace_editor** — file viewing/editing

Safety model:
  - By default, all actions run inside a Docker container (sandbox).
  - A COMPUTER_USE_SANDBOX=false env var allows local execution (dangerous).
  - Every action is logged to data/shared/computer_use_log.jsonl.

Requirements for sandbox mode:
  - Docker must be installed and running.
  - The sandbox image (default: ghcr.io/anthropics/anthropic-quickstarts:computer-use-demo)
    must be pulled or built locally.
  - Alternatively, set COMPUTER_USE_IMAGE to a custom image name.

Standalone usage (for testing):
  python -m src.tools.computer_use
"""

import base64
import io
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Try to import optional dependencies for local (non-sandbox) mode
try:
    from PIL import ImageGrab  # type: ignore
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

try:
    import pyautogui  # type: ignore
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_SANDBOX_ENABLED = os.environ.get("COMPUTER_USE_SANDBOX", "true").lower() == "true"
_SANDBOX_IMAGE = os.environ.get("COMPUTER_USE_IMAGE", "orion-sandbox")
_SANDBOX_CONTAINER = os.environ.get("COMPUTER_USE_CONTAINER", "orion-sandbox")
_SANDBOX_WORKSPACE = os.environ.get("ORION_WORKSPACE_PATH", r"C:\orion-workspace")
_LOG_PATH = os.path.join("data", "shared", "computer_use_log.jsonl")


def _log_action(action_type: str, action: dict, result: str) -> None:
    """Append an action record to the audit log."""
    os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": action_type,
        "action": action,
        "result_preview": result[:500] if result else "",
    }
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ===================================================================
#  Sandbox (Docker) executor
# ===================================================================
class _SandboxExecutor:
    """Runs Computer Use actions inside a Docker container."""

    def __init__(self, image: str = _SANDBOX_IMAGE, container: str = _SANDBOX_CONTAINER):
        self.image = image
        self.container = container

    def ensure_running(self) -> None:
        """Start the sandbox container if not already running."""
        check = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", self.container],
            capture_output=True, text=True,
        )
        if check.returncode != 0 or "true" not in check.stdout.lower():
            print(f"[computer_use] Container '{self.container}' not running.")
            print(f"[computer_use] Start it with: .\\sandbox\\sandbox.ps1 start")
            print(f"[computer_use] Attempting docker compose start ...")
            sandbox_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "sandbox"
            )
            compose_file = os.path.normpath(
                os.path.join(sandbox_dir, "docker-compose.yml")
            )
            if os.path.exists(compose_file):
                subprocess.run(
                    ["docker", "compose", "-f", compose_file, "up", "-d"],
                    check=True,
                )
            else:
                # Fallback: start standalone container with workspace mount
                workspace = _SANDBOX_WORKSPACE.replace("\\", "/")
                subprocess.run(
                    [
                        "docker", "run", "-d",
                        "--name", self.container,
                        "-v", f"{workspace}:/workspace",
                        "--cpus", "4",
                        "--memory", "4g",
                        "--security-opt", "no-new-privileges:true",
                        self.image,
                    ],
                    check=True,
                )
            time.sleep(3)  # let it boot

    def exec_bash(self, command: str) -> str:
        """Run a bash command inside the sandbox."""
        self.ensure_running()
        result = subprocess.run(
            ["docker", "exec", self.container, "bash", "-c", command],
            capture_output=True, text=True, timeout=120,
        )
        output = result.stdout
        if result.returncode != 0:
            output += f"\n[stderr] {result.stderr}" if result.stderr else ""
            output += f"\n[exit code {result.returncode}]"
        return output.strip()

    def screenshot(self) -> str:
        """Take a screenshot inside the sandbox, return base64 PNG."""
        self.ensure_running()
        result = subprocess.run(
            [
                "docker", "exec", self.container,
                "python3", "-c",
                "import subprocess, base64, sys; "
                "subprocess.run(['scrot', '/tmp/_screenshot.png'], check=True); "
                "data = open('/tmp/_screenshot.png','rb').read(); "
                "sys.stdout.write(base64.b64encode(data).decode())",
            ],
            capture_output=True, text=True, timeout=30,
        )
        return result.stdout.strip()

    def mouse_action(self, action: str, x: int, y: int, button: str = "left") -> str:
        """Perform mouse actions via xdotool in the sandbox."""
        self.ensure_running()
        if action == "click":
            btn_map = {"left": "1", "middle": "2", "right": "3"}
            cmd = f"xdotool mousemove {x} {y} click {btn_map.get(button, '1')}"
        elif action == "double_click":
            btn_map = {"left": "1", "middle": "2", "right": "3"}
            cmd = f"xdotool mousemove {x} {y} click --repeat 2 {btn_map.get(button, '1')}"
        elif action == "move":
            cmd = f"xdotool mousemove {x} {y}"
        else:
            return f"Unknown mouse action: {action}"

        return self.exec_bash(cmd)

    def keyboard_action(self, text: str = "", key: str = "") -> str:
        """Type text or press keys via xdotool in the sandbox."""
        self.ensure_running()
        if text:
            # Escape single quotes for bash
            escaped = text.replace("'", "'\\''")
            cmd = f"xdotool type -- '{escaped}'"
        elif key:
            # Map common key names to xdotool names
            key_map = {
                "enter": "Return", "return": "Return",
                "tab": "Tab", "escape": "Escape",
                "backspace": "BackSpace", "delete": "Delete",
                "up": "Up", "down": "Down", "left": "Left", "right": "Right",
                "space": "space", "ctrl+c": "ctrl+c",
            }
            xdo_key = key_map.get(key.lower(), key)
            cmd = f"xdotool key {xdo_key}"
        else:
            return "No text or key provided"

        return self.exec_bash(cmd)

    def scroll(self, x: int, y: int, direction: str = "down", amount: int = 3) -> str:
        """Scroll at position via xdotool."""
        self.ensure_running()
        btn = "5" if direction == "down" else "4"
        cmd = f"xdotool mousemove {x} {y} click --repeat {amount} {btn}"
        return self.exec_bash(cmd)


# ===================================================================
#  Local executor (non-sandbox, use with caution)
# ===================================================================
class _LocalExecutor:
    """Runs Computer Use actions directly on the host (DANGEROUS)."""

    def exec_bash(self, command: str) -> str:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=120,
        )
        output = result.stdout
        if result.returncode != 0:
            output += f"\n[stderr] {result.stderr}" if result.stderr else ""
            output += f"\n[exit code {result.returncode}]"
        return output.strip()

    def screenshot(self) -> str:
        if not _HAS_PIL:
            return "ERROR: Pillow not installed — cannot take screenshots locally"
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    def mouse_action(self, action: str, x: int, y: int, button: str = "left") -> str:
        if not _HAS_PYAUTOGUI:
            return "ERROR: pyautogui not installed"
        if action == "click":
            pyautogui.click(x, y, button=button)
        elif action == "double_click":
            pyautogui.doubleClick(x, y, button=button)
        elif action == "move":
            pyautogui.moveTo(x, y)
        else:
            return f"Unknown mouse action: {action}"
        return f"OK: {action} at ({x}, {y})"

    def keyboard_action(self, text: str = "", key: str = "") -> str:
        if not _HAS_PYAUTOGUI:
            return "ERROR: pyautogui not installed"
        if text:
            pyautogui.typewrite(text, interval=0.02)
        elif key:
            pyautogui.press(key)
        return f"OK: typed/pressed"

    def scroll(self, x: int, y: int, direction: str = "down", amount: int = 3) -> str:
        if not _HAS_PYAUTOGUI:
            return "ERROR: pyautogui not installed"
        clicks = -amount if direction == "down" else amount
        pyautogui.moveTo(x, y)
        pyautogui.scroll(clicks)
        return f"OK: scroll {direction} {amount}"


# ===================================================================
#  Unified Computer Use handler
# ===================================================================
def _get_executor():
    if _SANDBOX_ENABLED:
        return _SandboxExecutor()
    return _LocalExecutor()


def handle_computer_action(action: Dict[str, Any]) -> Dict[str, Any]:
    """Process a Computer Use tool_use block from Claude.

    Parameters
    ----------
    action : dict
        The ``input`` dict from Claude's tool_use content block.
        For the "computer" tool this includes fields like
        ``action``, ``coordinate``, ``text``.

    Returns
    -------
    dict
        A result dict suitable for returning as a tool_result content block,
        including base64 screenshots when applicable.
    """
    executor = _get_executor()
    act = action.get("action", "")

    try:
        if act == "screenshot":
            b64 = executor.screenshot()
            _log_action("computer", action, f"screenshot ({len(b64)} chars b64)")
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": b64,
                },
            }

        elif act in ("click", "double_click", "move"):
            coord = action.get("coordinate", [0, 0])
            x, y = int(coord[0]), int(coord[1])
            button = action.get("button", "left") if act != "move" else "left"
            result = executor.mouse_action(act, x, y, button)
            _log_action("computer", action, result)
            return {"type": "text", "text": result or "OK"}

        elif act == "type":
            text = action.get("text", "")
            result = executor.keyboard_action(text=text)
            _log_action("computer", action, result)
            return {"type": "text", "text": result or "OK"}

        elif act == "key":
            key = action.get("text", "")
            result = executor.keyboard_action(key=key)
            _log_action("computer", action, result)
            return {"type": "text", "text": result or "OK"}

        elif act == "scroll":
            coord = action.get("coordinate", [960, 540])
            x, y = int(coord[0]), int(coord[1])
            direction = action.get("direction", "down")
            amount = action.get("amount", 3)
            result = executor.scroll(x, y, direction, amount)
            _log_action("computer", action, result)
            return {"type": "text", "text": result or "OK"}

        else:
            msg = f"Unknown computer action: {act}"
            _log_action("computer", action, msg)
            return {"type": "text", "text": msg}

    except Exception as e:
        msg = f"Computer action error: {e}"
        _log_action("computer", action, msg)
        return {"type": "text", "text": msg}


def handle_bash_action(action: Dict[str, Any]) -> str:
    """Execute a bash command via Computer Use."""
    executor = _get_executor()
    command = action.get("command", "")
    if not command:
        return "No command provided"

    try:
        result = executor.exec_bash(command)
        _log_action("bash", action, result)
        return result
    except Exception as e:
        msg = f"Bash error: {e}"
        _log_action("bash", action, msg)
        return msg


def handle_editor_action(action: Dict[str, Any]) -> str:
    """Handle str_replace_editor actions (view, create, replace, insert)."""
    executor = _get_executor()
    command = action.get("command", "")
    path = action.get("path", "")

    try:
        if command == "view":
            view_range = action.get("view_range")
            if view_range:
                start, end = view_range
                bash_cmd = f"sed -n '{start},{end}p' '{path}'"
            else:
                bash_cmd = f"cat '{path}'"
            result = executor.exec_bash(bash_cmd)

        elif command == "create":
            file_text = action.get("file_text", "")
            escaped = file_text.replace("'", "'\\''")
            bash_cmd = f"mkdir -p $(dirname '{path}') && cat > '{path}' << 'HEREDOC_EOF'\n{file_text}\nHEREDOC_EOF"
            result = executor.exec_bash(bash_cmd)

        elif command == "str_replace":
            old_str = action.get("old_str", "")
            new_str = action.get("new_str", "")
            # Use Python inside the sandbox for reliable string replacement
            py_cmd = (
                f"import pathlib; p = pathlib.Path('{path}'); "
                f"t = p.read_text(); "
                f"old = '''{old_str}'''; new = '''{new_str}'''; "
                f"assert old in t, 'old_str not found'; "
                f"p.write_text(t.replace(old, new, 1)); "
                f"print('OK: replaced')"
            )
            result = executor.exec_bash(f'python3 -c "{py_cmd}"')

        elif command == "insert":
            insert_line = action.get("insert_line", 0)
            new_str = action.get("new_str", "")
            escaped = new_str.replace("'", "'\\''")
            bash_cmd = f"sed -i '{insert_line}a\\{escaped}' '{path}'"
            result = executor.exec_bash(bash_cmd)

        else:
            result = f"Unknown editor command: {command}"

        _log_action("editor", action, result)
        return result

    except Exception as e:
        msg = f"Editor error: {e}"
        _log_action("editor", action, msg)
        return msg


# ===================================================================
#  Runtime tool class (integrates with ToolRegistry)
# ===================================================================
class ComputerUseTool:
    """Exposes Computer Use as a dispatchable tool in the agent runtime.

    NOTE: Unlike the low-level handlers above, this tool is mainly a
    pass-through dispatcher.  The actual Computer Use actions come from
    Claude's built-in tool types (computer_20241022, bash_20241022,
    str_replace_editor_20241022), which the AnthropicClient handles
    at the provider level.  This tool is registered so that:
      1. The runtime can log and gate Computer Use actions.
      2. Agents can explicitly request computer actions via the
         standard tool-call pipeline.
    """

    @staticmethod
    def definition() -> dict:
        return {
            "name": "computer_use",
            "description": (
                "Execute actions on a sandboxed computer environment. "
                "Supports sub-commands: screenshot, click, type, key, "
                "scroll, bash, view_file, edit_file. "
                "All actions are logged and sandboxed by default."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_type": {
                        "type": "string",
                        "enum": ["computer", "bash", "str_replace_editor"],
                        "description": "Which Computer Use tool to invoke",
                    },
                    "action": {
                        "type": "object",
                        "description": "The action payload (varies by tool_type)",
                    },
                },
                "required": ["tool_type", "action"],
            },
        }

    @staticmethod
    def execute(arguments: dict) -> str:
        tool_type = arguments.get("tool_type", "")
        action = arguments.get("action", {})

        if tool_type == "computer":
            result = handle_computer_action(action)
            if isinstance(result, dict) and result.get("type") == "image":
                return f"[screenshot: {len(result['source']['data'])} bytes base64]"
            return result.get("text", str(result)) if isinstance(result, dict) else str(result)

        elif tool_type == "bash":
            return handle_bash_action(action)

        elif tool_type == "str_replace_editor":
            return handle_editor_action(action)

        else:
            return f"Unknown Computer Use tool_type: {tool_type}"


# ===================================================================
#  Standalone test
# ===================================================================
if __name__ == "__main__":
    print("Computer Use Tool — Test Mode")
    print(f"  Sandbox enabled: {_SANDBOX_ENABLED}")
    print(f"  Sandbox image:   {_SANDBOX_IMAGE}")
    print(f"  Container name:  {_SANDBOX_CONTAINER}")
    print()

    # Test bash
    result = handle_bash_action({"command": "echo Hello from Computer Use"})
    print(f"Bash test: {result}")
