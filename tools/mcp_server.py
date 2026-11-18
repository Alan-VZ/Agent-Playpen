"""Expose Playpen's tools through the shared UACP MCP transport."""

import argparse
import os
from pathlib import Path

from tools.gateway import build_gateway, default_registry
from universal_agent_control_plane.tool_mcp import GatewayMCPServer


def create_server(*, allowed_dirs=None, include_writes=False, database=None):
    registry = default_registry(
        allowed_dirs=allowed_dirs, include_writes=include_writes
    )
    gateway = build_gateway(registry, database=database)
    return GatewayMCPServer(gateway, "Agent Playpen Universal Tools")


def main():
    parser = argparse.ArgumentParser(description="Playpen tools over local MCP stdio")
    parser.add_argument("--allowed-dir", action="append", default=None)
    parser.add_argument("--allow-writes", action="store_true")
    parser.add_argument(
        "--data-dir",
        default=os.environ.get("PLAYPEN_TOOL_DATA_DIR", "traces/tool-gateway"),
    )
    args = parser.parse_args()
    server = create_server(
        allowed_dirs=args.allowed_dir,
        include_writes=args.allow_writes,
        database=Path(args.data_dir) / "tools.sqlite3",
    )
    server.run()


if __name__ == "__main__":
    main()
