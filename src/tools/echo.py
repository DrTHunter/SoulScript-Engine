"""Echo tool — safe demo tool for testing the tool-call pipeline."""


class EchoTool:
    """Returns whatever message it receives."""

    @staticmethod
    def definition() -> dict:
        return {
            "name": "echo",
            "description": "Echoes back the provided message. Safe demo tool for testing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message to echo back",
                    }
                },
                "required": ["message"],
            },
        }

    @staticmethod
    def execute(arguments: dict) -> str:
        return arguments.get("message", "")
