"""
movies_mcp_server.py

MCP server that exposes Movies tools to a Strands agent.
All data is fetched from the Movies FastAPI (:8080) — no direct DuckDB access.

Run:
    python movies_mcp_server.py          # stdio transport (used by Strands)
"""

import os
import httpx
from fastmcp import FastMCP
from fastmcp.client import StreamableHttpTransport

API_BASE_URL = os.getenv("MOVIES_API_BASE_URL", "http://localhost:8080")
client = httpx.AsyncClient(base_url=API_BASE_URL)
openapi_spec = httpx.get("http://localhost:8080/openapi.json").json()
transport = StreamableHttpTransport(url="https://api.example.com/mcp")

# Create the MCP server
mcp = FastMCP.from_openapi(
    openapi_spec=openapi_spec,
    client=client,
    name="My API Server"
)

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)