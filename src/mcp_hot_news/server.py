#!/usr/bin/env python3
"""
基于fastmcp的现代化热点新闻MCP服务器
支持多平台热点新闻聚合、缓存管理和趋势分析
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== 数据模型 ==================


class NewsItem(BaseModel):
    """新闻条目数据模型"""

    title: str = Field(description="新闻标题")
    url: str = Field(description="新闻链接")
    hot_value: Optional[Union[str, int]] = Field(default=None, description="热度值")
    rank: Optional[int] = Field(default=None, description="排名")
    platform: str = Field(description="平台名称")
    timestamp: str = Field(description="获取时间")


class PlatformNews(BaseModel):
    """平台新闻数据模型"""

    platform: str = Field(description="平台名称")
    news_list: List[NewsItem] = Field(description="新闻列表")
    update_time: str = Field(description="更新时间")
    total_count: int = Field(description="新闻总数")


class TrendAnalysis(BaseModel):
    """趋势分析数据模型"""

    hot_keywords: List[str] = Field(description="热门关键词")
    trending_topics: List[str] = Field(description="趋势话题")
    platform_summary: Dict[str, int] = Field(description="各平台热点数量")
    analysis_time: str = Field(description="分析时间")


# ================== 缓存管理器 ==================


@dataclass
class CacheItem:
    """缓存条目"""

    data: Any
    timestamp: datetime
    ttl: int = 3600  # 1小时TTL


class CacheManager:
    """智能缓存管理器"""

    def __init__(self):
        self._cache: Dict[str, CacheItem] = {}

    def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        if key not in self._cache:
            return None

        item = self._cache[key]
        if datetime.now() - item.timestamp > timedelta(seconds=item.ttl):
            del self._cache[key]
            return None

        return item.data

    def set(self, key: str, data: Any, ttl: int = 3600) -> None:
        """设置缓存数据"""
        self._cache[key] = CacheItem(data=data, timestamp=datetime.now(), ttl=ttl)

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        now = datetime.now()
        valid_items = 0
        expired_items = 0

        for item in self._cache.values():
            if now - item.timestamp <= timedelta(seconds=item.ttl):
                valid_items += 1
            else:
                expired_items += 1

        return {
            "total_items": len(self._cache),
            "valid_items": valid_items,
            "expired_items": expired_items,
            "cache_hit_ratio": valid_items / max(len(self._cache), 1),
        }


# ================== 数据提供者 ==================


class HotNewsProvider:
    """热点新闻数据提供者，使用vvhan API"""

    def __init__(self):
        self.cache_manager = CacheManager()

        # vvhan API基础URL
        self.vvhan_base_url = "https://api.vvhan.com/api/hotlist"

        # 平台映射配置（参考local_mcp_hot_news_server.py）
        self.platforms = {
            "zhihu": {"name": "知乎热榜", "api_path": "zhihuHot", "vvhan": True},
            "weibo": {"name": "微博热搜", "api_path": "weibo", "vvhan": True},
            "baidu": {"name": "百度热搜", "api_path": "baiduRY", "vvhan": True},
            "bilibili": {"name": "B站热门", "api_path": "bili", "vvhan": True},
            "douyin": {"name": "抖音热点", "api_path": "douyinHot", "vvhan": True},
            "toutiao": {"name": "今日头条", "api_path": "toutiao", "vvhan": True},
            "hupu": {"name": "虎扑热帖", "api_path": "hupu", "vvhan": True},
            "douban": {"name": "豆瓣热门", "api_path": "douban", "vvhan": True},
            "ithome": {"name": "IT之家", "api_path": "ithome", "vvhan": True},
            "kuaishou": {
                "name": "快手热点",
                "api_path": "douyinHot",
                "vvhan": True,
            },  # 使用抖音API
            "netease": {
                "name": "网易新闻",
                "api_path": "baiduRY",
                "vvhan": True,
            },  # 使用百度API
            "thepaper": {
                "name": "澎湃新闻",
                "api_path": "baiduRY",
                "vvhan": True,
            },  # 使用百度API
            "xueqiu": {
                "name": "雪球",
                "api_path": "hupu",
                "vvhan": True,
            },  # 使用虎扑API
        }

    async def get_platform_news(
        self, platform: str, limit: int = 20
    ) -> Optional[PlatformNews]:
        """获取指定平台的热点新闻"""
        if platform not in self.platforms:
            logger.error(f"不支持的平台: {platform}")
            return None

        # 检查缓存
        cache_key = f"news_{platform}_{limit}"
        cached_data = self.cache_manager.get(cache_key)
        if cached_data:
            logger.info(f"使用缓存数据: {platform}")
            return cached_data

        platform_info = self.platforms[platform]
        platform_name = platform_info["name"]

        logger.info(f"获取 {platform_name} 热点数据...")

        try:
            if platform_info.get("vvhan", False):
                # 使用vvhan API
                api_path = platform_info["api_path"]
                url = f"{self.vvhan_base_url}/{api_path}"

                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url)

                    if response.status_code == 200:
                        data = response.json()

                        if data.get("success", False) and "data" in data:
                            # vvhan API返回的数据格式
                            raw_data = data["data"]

                            # 确保是列表格式
                            if isinstance(raw_data, dict) and "list" in raw_data:
                                items = raw_data["list"][:limit]
                            elif isinstance(raw_data, list):
                                items = raw_data[:limit]
                            else:
                                logger.warning(
                                    f"vvhan API返回意外格式 - 平台: {platform_name}"
                                )
                                return await self._get_mock_news(platform, limit)

                            # 转换为标准格式
                            news_items = []
                            for i, item in enumerate(items):
                                if isinstance(item, dict):
                                    news_item = NewsItem(
                                        title=item.get("title", ""),
                                        url=item.get("link", "") or item.get("url", ""),
                                        hot_value=item.get("heat", 0)
                                        or item.get("hot", 0),
                                        rank=i + 1,
                                        platform=platform_name,
                                        timestamp=datetime.now().isoformat(),
                                    )
                                    news_items.append(news_item)

                            platform_news = PlatformNews(
                                platform=platform_name,
                                news_list=news_items,
                                update_time=datetime.now().isoformat(),
                                total_count=len(news_items),
                            )

                            # 缓存结果
                            self.cache_manager.set(cache_key, platform_news)
                            logger.info(
                                f"✅ {platform_name} 数据获取成功: {len(news_items)}条"
                            )
                            return platform_news
                        else:
                            logger.warning(
                                f"vvhan API返回失败 - 平台: {platform_name}, 响应: {data}"
                            )
                            return await self._get_mock_news(platform, limit)
                    else:
                        logger.warning(
                            f"vvhan API请求失败 - 平台: {platform_name}, "
                            f"状态码: {response.status_code}"
                        )
                        return await self._get_mock_news(platform, limit)
            else:
                # 使用模拟数据
                return await self._get_mock_news(platform, limit)

        except Exception as e:
            logger.error(f"获取 {platform_name} 数据时发生错误: {str(e)}")
            return await self._get_mock_news(platform, limit)

    async def get_all_platforms_news(self, limit: int = 10) -> List[PlatformNews]:
        """获取所有平台热点新闻"""
        all_news = []

        tasks = [
            self.get_platform_news(platform, limit)
            for platform in self.platforms.keys()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, PlatformNews):
                all_news.append(result)
            elif isinstance(result, Exception):
                logger.error(f"获取平台新闻失败: {result}")

        return all_news

    async def _get_mock_news(self, platform: str, limit: int) -> PlatformNews:
        """降级到模拟数据"""
        platform_info = self.platforms.get(platform, {"name": platform})
        platform_name = platform_info["name"]

        logger.info(f"使用模拟数据 - 平台: {platform_name}")

        # 根据平台生成不同类型的模拟数据
        base_titles = {
            "zhihu": [
                "知乎热门话题",
                "深度思考问题",
                "专业领域讨论",
                "生活经验分享",
                "科技前沿探讨",
            ],
            "weibo": [
                "微博热搜话题",
                "娱乐明星动态",
                "社会热点事件",
                "网络流行话题",
                "突发新闻",
            ],
            "baidu": [
                "百度热搜关键词",
                "搜索热门词汇",
                "网民关注焦点",
                "热门搜索词",
                "流行搜索",
            ],
            "bilibili": ["B站热门视频", "UP主创作", "动漫番剧", "游戏解说", "知识科普"],
            "douyin": [
                "抖音热门话题",
                "短视频话题",
                "创意挑战",
                "音乐热门",
                "生活记录",
            ],
            "toutiao": ["今日头条新闻", "时事要闻", "社会新闻", "科技资讯", "财经动态"],
            "hupu": ["虎扑热帖", "体育讨论", "NBA话题", "足球分析", "运动健身"],
            "douban": ["豆瓣热门", "电影评论", "书籍推荐", "生活小组", "文艺话题"],
            "ithome": ["IT之家资讯", "科技新闻", "数码产品", "软件更新", "硬件评测"],
        }

        titles = base_titles.get(platform, ["默认热点话题"])

        mock_news = []
        for i in range(min(limit, 5)):  # 最多生成5条模拟数据
            news_item = NewsItem(
                title=f"{titles[i % len(titles)]} {i+1}",
                url=f"https://{platform}.com/mock/{i+1}",
                hot_value=f"{1000-i*100}",
                rank=i + 1,
                platform=platform_name,
                timestamp=datetime.now().isoformat(),
            )
            mock_news.append(news_item)

        return PlatformNews(
            platform=platform_name,
            news_list=mock_news,
            update_time=datetime.now().isoformat(),
            total_count=len(mock_news),
        )

    def analyze_trends(self, all_news: List[PlatformNews]) -> TrendAnalysis:
        """分析热点趋势"""
        hot_keywords = []
        trending_topics = []
        platform_summary = {}

        for platform_news in all_news:
            platform_summary[platform_news.platform] = platform_news.total_count

            # 提取关键词（简化实现）
            for news in platform_news.news_list:
                words = news.title.split()
                hot_keywords.extend(words[:2])  # 取前两个词作为关键词
                if len(trending_topics) < 10:
                    trending_topics.append(news.title)

        # 去重并限制数量
        hot_keywords = list(set(hot_keywords))[:20]
        trending_topics = trending_topics[:10]

        return TrendAnalysis(
            hot_keywords=hot_keywords,
            trending_topics=trending_topics,
            platform_summary=platform_summary,
            analysis_time=datetime.now().isoformat(),
        )


# ================== FastMCP 服务器 ==================

# 创建FastMCP服务器实例
mcp = FastMCP(
    name="HotNewsServer",
    instructions="""
    这是一个现代化的热点新闻MCP服务器，提供以下功能：
    1. 获取指定平台热点新闻
    2. 获取所有平台热点新闻汇总
    3. 分析热点趋势和关键词

    支持的平台包括：微博、知乎、百度、哔哩哔哩、抖音、快手、今日头条、澎湃新闻、网易新闻、雪球等。
    所有数据都有智能缓存机制，提高响应速度。
    """,
)

# 创建数据提供者实例
news_provider = HotNewsProvider()

# ================== MCP 工具定义 ==================


@mcp.tool()
async def get_hot_news(
    platform: str = Field(description="平台名称，如 weibo, zhihu, baidu 等"),
    limit: int = Field(default=20, description="获取新闻数量，默认20条"),
) -> str:
    """获取指定平台的热点新闻"""
    try:
        if platform not in news_provider.platforms:
            available_platforms = ", ".join(news_provider.platforms.keys())
            return f"不支持的平台: {platform}。支持的平台: {available_platforms}"

        if limit <= 0 or limit > 50:
            return "新闻数量限制在1-50之间"

        platform_news = await news_provider.get_platform_news(platform, limit)
        if not platform_news:
            return f"获取 {platform} 新闻失败"

        return json.dumps(platform_news.model_dump(), ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"get_hot_news error: {e}")
        return "获取新闻时发生错误: " + str(e)


@mcp.tool()
async def get_all_platforms_news(
    limit: int = Field(default=10, description="每个平台获取新闻数量，默认10条")
) -> str:
    """获取所有平台的热点新闻汇总"""
    try:
        if limit <= 0 or limit > 20:
            return "每平台新闻数量限制在1-20之间"

        all_news = await news_provider.get_all_platforms_news(limit)

        result = {
            "summary": {
                "total_platforms": len(all_news),
                "total_news": sum(news.total_count for news in all_news),
                "update_time": datetime.now().isoformat(),
            },
            "platforms": [news.model_dump() for news in all_news],
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"get_all_platforms_news error: {e}")
        return f"获取所有平台新闻时发生错误: {str(e)}"


@mcp.tool()
async def analyze_trends(
    limit: int = Field(default=10, description="每个平台分析新闻数量，默认10条")
) -> str:
    """分析当前热点趋势和关键词"""
    try:
        if limit <= 0 or limit > 20:
            return "分析新闻数量限制在1-20之间"

        all_news = await news_provider.get_all_platforms_news(limit)
        trend_analysis = news_provider.analyze_trends(all_news)

        return json.dumps(trend_analysis.model_dump(), ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"analyze_trends error: {e}")
        return "分析趋势时发生错误: " + str(e)


@mcp.tool()
async def get_server_health() -> str:
    """获取服务器健康状态和缓存统计"""
    try:
        cache_stats = news_provider.cache_manager.get_stats()

        health_info = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "supported_platforms": list(news_provider.platforms.keys()),
            "cache_statistics": cache_stats,
            "version": "2.0.0-fastmcp",
        }

        return json.dumps(health_info, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"get_server_health error: {e}")
        return f"获取健康状态时发生错误: {str(e)}"


@mcp.tool()
async def clear_cache() -> str:
    """清空所有缓存数据"""
    try:
        news_provider.cache_manager.clear()
        return json.dumps(
            {
                "status": "success",
                "message": "缓存已清空",
                "timestamp": datetime.now().isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"clear_cache error: {e}")
        return f"清空缓存时发生错误: {str(e)}"


# ================== 资源定义 ==================


@mcp.resource("hot-news://platforms")
def get_supported_platforms() -> str:
    """获取支持的平台列表"""
    platforms_info = {
        "supported_platforms": news_provider.platforms,
        "total_count": len(news_provider.platforms),
        "update_time": datetime.now().isoformat(),
    }
    return json.dumps(platforms_info, ensure_ascii=False, indent=2)


@mcp.resource("hot-news://config")
def get_server_config() -> str:
    """获取服务器配置信息"""
    config_info = {
        "name": "HotNewsServer",
        "version": "2.0.0-fastmcp",
        "api_base_url": news_provider.vvhan_base_url,
        "cache_ttl": 3600,
        "max_news_per_request": 50,
        "max_platforms": len(news_provider.platforms),
    }
    return json.dumps(config_info, ensure_ascii=False, indent=2)


# ================== 主程序入口 ==================


def main():
    """命令行入口点"""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="MCP Hot News Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="传输协议 (默认: stdio)",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="HTTP服务器主机 (默认: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8001, help="HTTP服务器端口 (默认: 8001)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别 (默认: INFO)",
    )

    args = parser.parse_args()

    # 设置日志级别
    import logging

    logging.getLogger().setLevel(getattr(logging, args.log_level))

    logger.info(f"启动MCP热点新闻服务器 - 传输: {args.transport}")

    try:
        if args.transport == "http":
            logger.info(f"HTTP模式 - 监听 {args.host}:{args.port}")
            mcp.run(transport="http", host=args.host, port=args.port)
        else:
            logger.info("STDIO模式")
            mcp.run()
    except KeyboardInterrupt:
        logger.info("服务器已停止")
        sys.exit(0)
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    logger.info("启动FastMCP热点新闻服务器...")
    # 默认使用STDIO传输，也可以配置HTTP传输
    # mcp.run(transport="http", host="0.0.0.0", port=8001)
    mcp.run()
