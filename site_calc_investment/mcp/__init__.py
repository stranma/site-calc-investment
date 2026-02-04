"""MCP server for Site-Calc investment planning.

Exposes investment optimization tools to LLM agents via FastMCP.
Install with: pip install site-calc-investment[mcp]
"""

from site_calc_investment.mcp.server import mcp


def main() -> None:
    """Entry point for the MCP server."""
    mcp.run()


__all__ = ["main", "mcp"]
