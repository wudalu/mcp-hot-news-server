"""
MCP Hot News Server

一个基于FastMCP的现代化多平台热点新闻聚合服务器
A modern multi-platform hot news aggregation server based on FastMCP
"""

__version__ = "1.0.0"
__author__ = "ByteDance"
__email__ = "contact@example.com"

from .server import mcp, HotNewsProvider
from .client import HotNewsMCPClient

__all__ = [
    "mcp",
    "HotNewsProvider",
    "HotNewsMCPClient",
    "__version__",
]
