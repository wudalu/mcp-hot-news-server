#!/usr/bin/env python3
"""
基于fastmcp的热点新闻MCP客户端
提供异步客户端和LangChain工具适配器
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Union, AsyncContextManager
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastmcp import Client
from pydantic import BaseModel, Field

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== 数据模型 ==================

class NewsItem(BaseModel):
    """新闻条目数据模型"""
    title: str
    url: str
    hot_value: Optional[Union[str, int]] = None
    rank: Optional[int] = None
    platform: str
    timestamp: str

class PlatformNews(BaseModel):
    """平台新闻数据模型"""
    platform: str
    news_list: List[NewsItem]
    update_time: str
    total_count: int

class TrendAnalysis(BaseModel):
    """趋势分析数据模型"""
    hot_keywords: List[str]
    trending_topics: List[str]
    platform_summary: Dict[str, int]
    analysis_time: str

class HotNewsClientConfig(BaseModel):
    """客户端配置"""
    server_path: Optional[str] = None
    server_url: Optional[str] = None
    transport: str = "stdio"
    timeout: int = 30

# ================== FastMCP 客户端封装 ==================

class HotNewsMCPClient:
    """热点新闻MCP客户端"""
    
    def __init__(self, config: Optional[HotNewsClientConfig] = None):
        """初始化客户端"""
        self.config = config or HotNewsClientConfig()
        self._client: Optional[Client] = None
        self._setup_client()
    
    def _setup_client(self) -> None:
        """设置客户端连接"""
        try:
            if self.config.server_path:
                # 连接到本地Python服务器文件
                self._client = Client(self.config.server_path)
                logger.info(f"连接到本地服务器: {self.config.server_path}")
            elif self.config.server_url:
                # 连接到远程HTTP服务器
                self._client = Client(self.config.server_url)
                logger.info(f"连接到远程服务器: {self.config.server_url}")
            else:
                # 默认连接到本地服务器文件
                server_path = "mcp_servers/hot_news_server/server.py"
                self._client = Client(server_path)
                logger.info(f"使用默认服务器路径: {server_path}")
        except Exception as e:
            logger.error(f"设置客户端连接失败: {e}")
            raise
    
    @asynccontextmanager
    async def connect(self) -> AsyncContextManager['HotNewsMCPClient']:
        """异步上下文管理器，用于管理客户端连接"""
        if not self._client:
            raise RuntimeError("客户端未初始化")
        
        try:
            async with self._client:
                yield self
        except Exception as e:
            logger.error(f"客户端连接失败: {e}")
            raise
    
    async def get_hot_news(
        self, 
        platform: str, 
        limit: int = 20
    ) -> Optional[PlatformNews]:
        """获取指定平台热点新闻"""
        try:
            if not self._client:
                raise RuntimeError("客户端未连接")
            
            result = await self._client.call_tool(
                "get_hot_news",
                {"platform": platform, "limit": limit}
            )
            
            if result and result[0].text:
                data = json.loads(result[0].text)
                return PlatformNews(**data)
            
            return None
            
        except Exception as e:
            logger.error(f"获取热点新闻失败: {e}")
            return None
    
    async def get_all_platforms_news(self, limit: int = 10) -> List[PlatformNews]:
        """获取所有平台热点新闻"""
        try:
            if not self._client:
                raise RuntimeError("客户端未连接")
            
            result = await self._client.call_tool(
                "get_all_platforms_news",
                {"limit": limit}
            )
            
            if result and result[0].text:
                data = json.loads(result[0].text)
                platforms_data = data.get("platforms", [])
                return [PlatformNews(**platform) for platform in platforms_data]
            
            return []
            
        except Exception as e:
            logger.error(f"获取所有平台新闻失败: {e}")
            return []
    
    async def analyze_trends(self, limit: int = 10) -> Optional[TrendAnalysis]:
        """分析热点趋势"""
        try:
            if not self._client:
                raise RuntimeError("客户端未连接")
            
            result = await self._client.call_tool(
                "analyze_trends",
                {"limit": limit}
            )
            
            if result and result[0].text:
                data = json.loads(result[0].text)
                return TrendAnalysis(**data)
            
            return None
            
        except Exception as e:
            logger.error(f"分析趋势失败: {e}")
            return None
    
    async def get_server_health(self) -> Dict[str, Any]:
        """获取服务器健康状态"""
        try:
            if not self._client:
                raise RuntimeError("客户端未连接")
            
            result = await self._client.call_tool("get_server_health", {})
            
            if result and result[0].text:
                return json.loads(result[0].text)
            
            return {"status": "unknown"}
            
        except Exception as e:
            logger.error(f"获取服务器健康状态失败: {e}")
            return {"status": "error", "error": str(e)}
    
    async def clear_cache(self) -> bool:
        """清空服务器缓存"""
        try:
            if not self._client:
                raise RuntimeError("客户端未连接")
            
            result = await self._client.call_tool("clear_cache", {})
            
            if result and result[0].text:
                data = json.loads(result[0].text)
                return data.get("status") == "success"
            
            return False
            
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
            return False
    
    async def list_tools(self) -> List[str]:
        """列出可用工具"""
        try:
            if not self._client:
                raise RuntimeError("客户端未连接")
            
            tools = await self._client.list_tools()
            return [tool.name for tool in tools]
            
        except Exception as e:
            logger.error(f"列出工具失败: {e}")
            return []
    
    async def ping_server(self) -> bool:
        """测试服务器连接"""
        try:
            if not self._client:
                return False
            
            await self._client.ping()
            return True
            
        except Exception as e:
            logger.error(f"Ping服务器失败: {e}")
            return False

# ================== LangChain 工具适配器 ==================

class HotNewsToolAdapter:
    """热点新闻工具的LangChain适配器"""
    
    def __init__(self, client_config: Optional[HotNewsClientConfig] = None):
        """初始化适配器"""
        self.client = HotNewsMCPClient(client_config)
        self._connection_context = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._connection_context = self.client.connect()
        self.connected_client = await self._connection_context.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self._connection_context:
            await self._connection_context.__aexit__(exc_type, exc_val, exc_tb)
    
    async def get_hot_news_formatted(
        self, 
        platform: str, 
        limit: int = 20,
        format_type: str = "summary"
    ) -> str:
        """获取格式化的热点新闻"""
        try:
            news_data = await self.connected_client.get_hot_news(platform, limit)
            
            if not news_data:
                return f"无法获取 {platform} 的热点新闻"
            
            if format_type == "summary":
                return self._format_news_summary(news_data)
            elif format_type == "detailed":
                return self._format_news_detailed(news_data)
            elif format_type == "json":
                return json.dumps(news_data.model_dump(), ensure_ascii=False, indent=2)
            else:
                return self._format_news_summary(news_data)
                
        except Exception as e:
            logger.error(f"获取格式化新闻失败: {e}")
            return f"获取新闻时发生错误: {str(e)}"
    
    async def get_all_news_formatted(
        self, 
        limit: int = 10,
        format_type: str = "summary"
    ) -> str:
        """获取所有平台格式化新闻"""
        try:
            all_news = await self.connected_client.get_all_platforms_news(limit)
            
            if not all_news:
                return "无法获取任何平台的热点新闻"
            
            if format_type == "summary":
                return self._format_all_news_summary(all_news)
            elif format_type == "detailed":
                return self._format_all_news_detailed(all_news)
            elif format_type == "json":
                return json.dumps([news.model_dump() for news in all_news], ensure_ascii=False, indent=2)
            else:
                return self._format_all_news_summary(all_news)
                
        except Exception as e:
            logger.error(f"获取所有平台新闻失败: {e}")
            return f"获取新闻时发生错误: {str(e)}"
    
    async def analyze_trends_formatted(
        self, 
        limit: int = 10,
        format_type: str = "summary"
    ) -> str:
        """获取格式化的趋势分析"""
        try:
            trend_data = await self.connected_client.analyze_trends(limit)
            
            if not trend_data:
                return "无法获取趋势分析数据"
            
            if format_type == "summary":
                return self._format_trends_summary(trend_data)
            elif format_type == "detailed":
                return self._format_trends_detailed(trend_data)
            elif format_type == "json":
                return json.dumps(trend_data.model_dump(), ensure_ascii=False, indent=2)
            else:
                return self._format_trends_summary(trend_data)
                
        except Exception as e:
            logger.error(f"分析趋势失败: {e}")
            return f"分析趋势时发生错误: {str(e)}"
    
    def _format_news_summary(self, news_data: PlatformNews) -> str:
        """格式化新闻摘要"""
        summary = f"## {news_data.platform} 热点新闻 ({news_data.total_count}条)\n\n"
        
        for i, news in enumerate(news_data.news_list[:10], 1):
            summary += f"{i}. **{news.title}**\n"
            if news.hot_value:
                summary += f"   🔥 热度: {news.hot_value}\n"
            if news.url:
                summary += f"   🔗 链接: {news.url}\n"
            summary += "\n"
        
        summary += f"*更新时间: {news_data.update_time}*"
        return summary
    
    def _format_news_detailed(self, news_data: PlatformNews) -> str:
        """格式化详细新闻"""
        detailed = f"# {news_data.platform} 详细热点新闻报告\n\n"
        detailed += f"**总数**: {news_data.total_count}条\n"
        detailed += f"**更新时间**: {news_data.update_time}\n\n"
        
        for news in news_data.news_list:
            detailed += f"## 第{news.rank}名: {news.title}\n\n"
            detailed += f"- **平台**: {news.platform}\n"
            if news.hot_value:
                detailed += f"- **热度值**: {news.hot_value}\n"
            if news.url:
                detailed += f"- **原文链接**: {news.url}\n"
            detailed += f"- **抓取时间**: {news.timestamp}\n\n"
            detailed += "---\n\n"
        
        return detailed
    
    def _format_all_news_summary(self, all_news: List[PlatformNews]) -> str:
        """格式化所有平台新闻摘要"""
        total_news = sum(news.total_count for news in all_news)
        summary = f"# 全平台热点新闻汇总\n\n"
        summary += f"**覆盖平台**: {len(all_news)}个\n"
        summary += f"**新闻总数**: {total_news}条\n\n"
        
        for platform_news in all_news:
            summary += f"## {platform_news.platform} (Top 5)\n\n"
            for i, news in enumerate(platform_news.news_list[:5], 1):
                summary += f"{i}. {news.title}\n"
                if news.hot_value:
                    summary += f"   🔥 {news.hot_value}\n"
            summary += "\n"
        
        return summary
    
    def _format_all_news_detailed(self, all_news: List[PlatformNews]) -> str:
        """格式化所有平台详细新闻"""
        detailed = "# 全平台详细热点新闻报告\n\n"
        
        for platform_news in all_news:
            detailed += self._format_news_detailed(platform_news)
            detailed += "\n" + "="*50 + "\n\n"
        
        return detailed
    
    def _format_trends_summary(self, trend_data: TrendAnalysis) -> str:
        """格式化趋势分析摘要"""
        summary = f"# 热点趋势分析报告\n\n"
        summary += f"**分析时间**: {trend_data.analysis_time}\n\n"
        
        summary += "## 🔥 热门关键词 (Top 10)\n\n"
        for i, keyword in enumerate(trend_data.hot_keywords[:10], 1):
            summary += f"{i}. {keyword}\n"
        
        summary += "\n## 📈 趋势话题 (Top 5)\n\n"
        for i, topic in enumerate(trend_data.trending_topics[:5], 1):
            summary += f"{i}. {topic}\n"
        
        summary += "\n## 📊 各平台热度分布\n\n"
        for platform, count in trend_data.platform_summary.items():
            summary += f"- **{platform}**: {count}条\n"
        
        return summary
    
    def _format_trends_detailed(self, trend_data: TrendAnalysis) -> str:
        """格式化详细趋势分析"""
        detailed = f"# 详细热点趋势分析报告\n\n"
        detailed += f"**分析时间**: {trend_data.analysis_time}\n\n"
        
        detailed += "## 🔍 完整关键词列表\n\n"
        for i, keyword in enumerate(trend_data.hot_keywords, 1):
            detailed += f"{i}. {keyword}\n"
        
        detailed += "\n## 📑 完整趋势话题列表\n\n"
        for i, topic in enumerate(trend_data.trending_topics, 1):
            detailed += f"{i}. {topic}\n"
        
        detailed += "\n## 📈 平台热度统计分析\n\n"
        total_news = sum(trend_data.platform_summary.values())
        for platform, count in trend_data.platform_summary.items():
            percentage = (count / total_news * 100) if total_news > 0 else 0
            detailed += f"- **{platform}**: {count}条 ({percentage:.1f}%)\n"
        
        detailed += f"\n**总计**: {total_news}条新闻\n"
        
        return detailed

# ================== 便捷函数 ==================

async def create_hot_news_client(
    server_path: Optional[str] = None,
    server_url: Optional[str] = None,
    transport: str = "stdio"
) -> HotNewsMCPClient:
    """创建热点新闻客户端的便捷函数"""
    config = HotNewsClientConfig(
        server_path=server_path,
        server_url=server_url,
        transport=transport
    )
    return HotNewsMCPClient(config)

async def quick_get_news(
    platform: str, 
    limit: int = 20,
    server_path: Optional[str] = None
) -> Optional[PlatformNews]:
    """快速获取新闻的便捷函数"""
    client = await create_hot_news_client(server_path=server_path)
    
    async with client.connect():
        return await client.get_hot_news(platform, limit)

# ================== 测试和示例 ==================

async def test_client():
    """测试客户端功能"""
    print("🧪 测试FastMCP热点新闻客户端...")
    
    # 创建客户端
    client = await create_hot_news_client()
    
    async with client.connect():
        # 1. 测试服务器连接
        print("\n1. 测试服务器连接...")
        is_alive = await client.ping_server()
        print(f"服务器状态: {'✅ 在线' if is_alive else '❌ 离线'}")
        
        # 2. 获取健康状态
        print("\n2. 获取服务器健康状态...")
        health = await client.get_server_health()
        print(f"健康状态: {health.get('status', 'unknown')}")
        
        # 3. 列出可用工具
        print("\n3. 列出可用工具...")
        tools = await client.list_tools()
        print(f"可用工具: {', '.join(tools)}")
        
        # 4. 获取微博热点新闻
        print("\n4. 获取微博热点新闻...")
        weibo_news = await client.get_hot_news("weibo", 5)
        if weibo_news:
            print(f"获取到 {weibo_news.total_count} 条微博新闻")
            for i, news in enumerate(weibo_news.news_list[:3], 1):
                print(f"  {i}. {news.title}")
        
        # 5. 分析趋势
        print("\n5. 分析热点趋势...")
        trends = await client.analyze_trends(5)
        if trends:
            print(f"热门关键词: {', '.join(trends.hot_keywords[:5])}")

if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_client()) 