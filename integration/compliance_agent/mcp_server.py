"""Single-tool MCP shell for the read-only Issue #39 Compliance Agent."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .agent import answer

mcp = FastMCP(
    "awsops Compliance Agent",
    instructions=(
        "Use ask_compliance_agent for current four-account S3 Block Public Access "
        "or restricted-SSH status, explanation and no-change planning. "
        "The tool returns the complete user-visible Markdown answer as one string. "
        "Echo that string unchanged: do not summarize, quote, explain or append to it. "
        "This tool has no remediation capability."
    ),
)


@mcp.tool()
def ask_compliance_agent(request: str) -> str:
    """Return the complete read-only user-visible Markdown answer."""
    return answer(request)["answer"]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
