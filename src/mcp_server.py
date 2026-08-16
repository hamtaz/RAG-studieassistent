"""MCP server: exposes the study assistant as a tool for MCP clients (e.g. Claude Desktop).

Wraps answer_question() directly rather than calling the FastAPI endpoint over
HTTP - same logic, no extra network hop and no need to run the API separately.
"""

from mcp.server.fastmcp import FastMCP

from src.cosmos_client import get_container
from src.generation import answer_question

mcp = FastMCP("studieassistent")


@mcp.tool()
def ask_study_assistant(question: str) -> dict:
    """Answer a question from the ingested course material, with page citations."""
    return answer_question(question, get_container())


if __name__ == "__main__":
    mcp.run()
