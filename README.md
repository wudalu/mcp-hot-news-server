# MCP Hot News Server

[![PyPI version](https://badge.fury.io/py/mcp-hot-news.svg)](https://badge.fury.io/py/mcp-hot-news)
[![Python Support](https://img.shields.io/pypi/pyversions/mcp-hot-news.svg)](https://pypi.org/project/mcp-hot-news/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

一个基于 [FastMCP](https://github.com/jlowin/fastmcp) 的现代化多平台热点新闻聚合服务器，支持实时获取各大平台热点数据。

A modern multi-platform hot news aggregation server based on [FastMCP](https://github.com/jlowin/fastmcp), supporting real-time hot topics data from major platforms.

## ✨ 特性 Features

- 🚀 **基于 FastMCP**：原生 MCP 协议支持，标准化的工具接口
- 🌐 **多平台支持**：知乎、微博、百度、哔哩哔哩、抖音等 13+ 平台
- ⚡ **智能缓存**：TTL 缓存机制，提高响应速度
- 🔄 **异步并发**：高性能异步数据获取
- 📊 **趋势分析**：自动提取热门关键词和趋势话题
- 🛡️ **降级机制**：API 失效时自动切换到模拟数据
- 🔧 **LangChain 集成**：完美适配 LangChain 工具生态

## 🚀 快速开始 Quick Start

### 安装 Installation

```bash
pip install mcp-hot-news
```

### 基础使用 Basic Usage

#### 1. 启动 MCP 服务器

```bash
# 启动服务器（STDIO 模式）
mcp-hot-news

# 或者 HTTP 模式
mcp-hot-news --transport http --host 0.0.0.0 --port 8001
```

#### 2. Python 代码调用

```python
import asyncio
from mcp_hot_news.client import HotNewsClient

async def main():
    async with HotNewsClient() as client:
        # 获取微博热搜
        weibo_news = await client.get_hot_news("weibo", limit=10)
        print(weibo_news)
        
        # 获取所有平台新闻
        all_news = await client.get_all_platforms_news(limit=5)
        print(all_news)
        
        # 分析热点趋势
        trends = await client.analyze_trends(limit=10)
        print(trends)

asyncio.run(main())
```

#### 3. LangChain 集成

```python
from mcp_hot_news.langchain import HotNewsToolAdapter
from langchain.agents import initialize_agent

# 创建工具适配器
hot_news_tools = HotNewsToolAdapter()

# 获取 LangChain 工具
tools = await hot_news_tools.get_langchain_tools()

# 集成到 Agent
agent = initialize_agent(tools, llm, agent="zero-shot-react-description")
```

## 📋 支持的平台 Supported Platforms

| 平台 Platform | 支持状态 Status | API 来源 API Source |
|---------------|----------------|---------------------|
| 知乎 Zhihu | ✅ | vvhan API |
| 微博 Weibo | ⚠️ | vvhan API (不稳定) |
| 百度 Baidu | ⚠️ | vvhan API (不稳定) |
| 哔哩哔哩 Bilibili | ✅ | vvhan API |
| 抖音 Douyin | ✅ | vvhan API |
| 快手 Kuaishou | ✅ | vvhan API |
| 今日头条 Toutiao | ✅ | vvhan API |
| 虎扑 Hupu | ⚠️ | vvhan API (不稳定) |
| 豆瓣 Douban | ✅ | vvhan API |
| IT之家 ITHome | ⚠️ | vvhan API (不稳定) |

> ⚠️ 注：部分平台 API 可能不稳定，会自动降级到模拟数据

## 🛠️ API 接口 API Reference

### MCP 工具 MCP Tools

#### `get_hot_news`
获取指定平台的热点新闻

**参数 Parameters:**
- `platform` (str): 平台名称
- `limit` (int): 获取数量，默认 20

#### `get_all_platforms_news`
获取所有平台的热点新闻汇总

**参数 Parameters:**
- `limit` (int): 每个平台获取数量，默认 10

#### `analyze_trends`
分析当前热点趋势和关键词

**参数 Parameters:**
- `limit` (int): 分析数量，默认 10

#### `get_server_health`
获取服务器健康状态

#### `clear_cache`
清空所有缓存数据

### 数据模型 Data Models

```python
class NewsItem:
    title: str              # 新闻标题
    url: str               # 新闻链接  
    hot_value: Optional[Union[str, int]]  # 热度值
    rank: Optional[int]     # 排名
    platform: str          # 平台名称
    timestamp: str         # 获取时间

class PlatformNews:
    platform: str          # 平台名称
    news_list: List[NewsItem]  # 新闻列表
    update_time: str       # 更新时间
    total_count: int       # 新闻总数

class TrendAnalysis:
    hot_keywords: List[str]     # 热门关键词
    trending_topics: List[str]  # 趋势话题
    platform_summary: Dict[str, int]  # 各平台热点数量
    analysis_time: str         # 分析时间
```

## 🔧 配置 Configuration

### 环境变量

```bash
# 缓存TTL（秒）
export MCP_CACHE_TTL=3600

# API请求超时（秒）
export MCP_REQUEST_TIMEOUT=10

# 日志级别
export MCP_LOG_LEVEL=INFO
```

### 自定义配置

```python
from mcp_hot_news.server import HotNewsProvider

# 自定义配置
provider = HotNewsProvider()
provider.cache_manager.default_ttl = 7200  # 2小时缓存
```

## 🧪 开发和测试 Development & Testing

### 安装开发依赖

```bash
pip install -e ".[dev]"
```

### 运行测试

```bash
pytest
```

### 代码格式化

```bash
black src/ tests/
flake8 src/ tests/
mypy src/
```

## 📝 使用场景 Use Cases

1. **AI Agent 工具**：为 LangChain/LangGraph Agent 提供实时热点数据
2. **内容创作**：获取热点话题进行内容创作
3. **舆情监控**：监控各平台热点趋势变化
4. **数据分析**：分析跨平台热点数据相关性
5. **API 服务**：作为微服务提供热点数据接口

## 🤝 贡献 Contributing

欢迎贡献代码！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详细信息。

Welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## 📄 许可证 License

MIT License - 详见 [LICENSE](LICENSE) 文件。

## 🙏 致谢 Acknowledgments

- [FastMCP](https://github.com/jlowin/fastmcp) - 优秀的 MCP 框架
- [vvhan API](https://api.vvhan.com/) - 热点数据 API 提供者
- [LangChain](https://github.com/langchain-ai/langchain) - AI 应用开发框架

## 📞 联系我们 Contact

- GitHub Issues: [提交问题](https://github.com/yourusername/mcp-hot-news-server/issues)
- Email: contact@example.com

---

**⭐ 如果这个项目对你有帮助，请给个 Star！**

**⭐ If this project helps you, please give it a Star!** 