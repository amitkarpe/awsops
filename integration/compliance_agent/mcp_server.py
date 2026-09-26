"""Single-tool MCP shell for the read-only Issue #39 Compliance Agent."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .agent import answer

mcp = FastMCP(
    "awsops Compliance Agent",
    instructions=(
        "Use ask_compliance_agent for current four-account S3 Block Public Access "
        "or restricted-SSH status, explanation and no-change planning. "
        "This Issue #39 tool has no remediation capability."
    ),
)


@mcp.tool()
def ask_compliance_agent(request: str) -> dict:
    """Answer from the exact current config2 4-account x 2-control evidence matrix."""
    return answer(request)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
