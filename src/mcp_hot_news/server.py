#!/usr/bin/env python3
"""
基于fastmcp的现代化热点新闻MCP服务器
支持多平台热点新闻聚合、缓存管理和趋势分析
支持国内平台（vvhan API）和全球平台（Google Trends、NewsAPI、Reddit、Twitter等）
"""

import asyncio
import json
import logging
import os
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

# 导入配置管理
from .config import mcp_config

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
    description: Optional[str] = Field(default="", description="新闻描述")
    source: Optional[str] = Field(default="", description="新闻来源")
    controversy_score: Optional[float] = Field(default=0.0, description="争议性分数")
    engagement_potential: Optional[float] = Field(default=0.0, description="互动潜力")


class PlatformNews(BaseModel):
    """平台新闻数据模型"""

    platform: str = Field(description="平台名称")
    news_list: List[NewsItem] = Field(description="新闻列表")
    update_time: str = Field(description="更新时间")
    total_count: int = Field(description="新闻总数")
    platform_type: str = Field(default="domestic", description="平台类型：domestic/global")


class TrendAnalysis(BaseModel):
    """趋势分析数据模型"""

    hot_keywords: List[str] = Field(description="热门关键词")
    trending_topics: List[str] = Field(description="趋势话题")
    platform_summary: Dict[str, int] = Field(description="各平台热点数量")
    analysis_time: str = Field(description="分析时间")
    controversy_analysis: Dict[str, Any] = Field(default_factory=dict, description="争议性分析")


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


# ================== 争议性分析器 ==================


class ControversyAnalyzer:
    """争议性分析器"""
    
    def __init__(self):
        # 争议性关键词权重
        self.controversy_keywords = {
            # 高争议性 (权重 1.0)
            "争议": 1.0, "批评": 1.0, "抗议": 1.0, "反对": 1.0, "冲突": 1.0,
            "scandal": 1.0, "controversy": 1.0, "protest": 1.0, "crisis": 1.0,
            
            # 中等争议性 (权重 0.7)
            "讨论": 0.7, "质疑": 0.7, "分歧": 0.7, "辩论": 0.7, "热议": 0.7,
            "debate": 0.7, "discussion": 0.7, "question": 0.7, "concern": 0.7,
            
            # 低争议性 (权重 0.5)
            "变化": 0.5, "新政": 0.5, "改革": 0.5, "调整": 0.5, "更新": 0.5,
            "change": 0.5, "reform": 0.5, "update": 0.5, "new": 0.5,
            
            # 社会话题 (权重 0.8)
            "房价": 0.8, "教育": 0.8, "就业": 0.8, "医疗": 0.8, "养老": 0.8,
            "housing": 0.8, "education": 0.8, "healthcare": 0.8, "employment": 0.8,
            
            # 情感词汇 (权重 0.6)
            "愤怒": 0.6, "不满": 0.6, "担心": 0.6, "焦虑": 0.6, "失望": 0.6,
            "angry": 0.6, "upset": 0.6, "worried": 0.6, "disappointed": 0.6
        }
    
    def calculate_controversy_score(self, text: str) -> float:
        """计算文本的争议性分数"""
        if not text:
            return 0.0
        
        text_lower = text.lower()
        score = 0.0
        word_count = 0
        
        for keyword, weight in self.controversy_keywords.items():
            if keyword in text_lower:
                score += weight
                word_count += 1
        
        # 标准化分数 (0-1之间)
        if word_count > 0:
            score = min(score / word_count, 1.0)
        
        # 如果包含问号或感叹号，增加争议性
        if "?" in text or "？" in text:
            score += 0.2
        if "!" in text or "！" in text:
            score += 0.1
        
        return min(score, 1.0)


# ================== 数据提供者 ==================


class HotNewsProvider:
    """热点新闻数据提供者，支持国内和全球平台"""

    def __init__(self):
        self.cache_manager = CacheManager()
        self.controversy_analyzer = ControversyAnalyzer()
        self.config = mcp_config  # 添加配置引用

        # vvhan API基础URL（国内平台）
        self.vvhan_base_url = "https://api.vvhan.com/api/hotlist"

        # 国内平台映射配置
        self.domestic_platforms = {
            "zhihu": {"name": "知乎热榜", "api_path": "zhihuHot", "vvhan": True},
            "weibo": {"name": "微博热搜", "api_path": "weibo", "vvhan": True},
            "baidu": {"name": "百度热搜", "api_path": "baiduRY", "vvhan": True},
            "bilibili": {"name": "B站热门", "api_path": "bili", "vvhan": True},
            "douyin": {"name": "抖音热点", "api_path": "douyinHot", "vvhan": True},
            "toutiao": {"name": "今日头条", "api_path": "toutiao", "vvhan": True},
            "hupu": {"name": "虎扑热帖", "api_path": "hupu", "vvhan": True},
            "douban": {"name": "豆瓣热门", "api_path": "douban", "vvhan": True},
            "ithome": {"name": "IT之家", "api_path": "ithome", "vvhan": True},
        }
        
        # 全球平台配置
        self.global_platforms = {
            "google_trends": {"name": "Google Trends", "type": "serpapi"},
            "news_api": {"name": "NewsAPI", "type": "newsapi"},
            "reddit": {"name": "Reddit", "type": "reddit"},
            "twitter": {"name": "Twitter/X", "type": "twitter"},
        }
        
        # 合并所有平台
        self.platforms = {**self.domestic_platforms, **self.global_platforms}

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
            # 国内平台使用vvhan API
            if platform in self.domestic_platforms:
                return await self._get_domestic_platform_news(platform, limit)
            # 全球平台使用各自的API
            elif platform in self.global_platforms:
                return await self._get_global_platform_news(platform, limit)
            else:
                return await self._get_mock_news(platform, limit)

        except Exception as e:
            logger.error(f"获取 {platform_name} 数据时发生错误: {str(e)}")
            return await self._get_mock_news(platform, limit)

    async def _get_domestic_platform_news(self, platform: str, limit: int) -> Optional[PlatformNews]:
        """获取国内平台新闻（使用vvhan API）"""
        platform_info = self.domestic_platforms[platform]
        platform_name = platform_info["name"]
        
        if platform_info.get("vvhan", False):
            # 使用vvhan API
            api_path = platform_info["api_path"]
            url = f"{self.vvhan_base_url}/{api_path}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                try:
                    response = await client.get(url)

                    if response.status_code == 200:
                        data = response.json()

                        # 检查API是否返回成功状态
                        if data.get("success") is True and "data" in data:
                            # vvhan API返回的数据格式
                            raw_data = data["data"]

                            # 处理不同的数据格式
                            items = []
                            if isinstance(raw_data, dict) and "list" in raw_data:
                                # 格式1: {"data": {"list": [...]}}
                                items = raw_data["list"][:limit]
                            elif isinstance(raw_data, list):
                                # 格式2: {"data": [...]}
                                items = raw_data[:limit]
                            else:
                                logger.warning(f"vvhan API返回意外格式 - 平台: {platform_name}, 数据类型: {type(raw_data)}")
                                return await self._get_mock_news(platform, limit)

                            # 转换为标准格式
                            news_items = []
                            for i, item in enumerate(items):
                                if isinstance(item, dict):
                                    title = item.get("title", "")
                                    if title:  # 只处理有标题的项目
                                        # 处理不同的字段名
                                        url_field = item.get("url") or item.get("link") or item.get("mobil_url", "")
                                        hot_field = item.get("hot") or item.get("heat") or item.get("index", 0)
                                        
                                        news_item = NewsItem(
                                            title=title,
                                            url=url_field,
                                            hot_value=hot_field,
                                            rank=i + 1,
                                            platform=platform_name,
                                            timestamp=datetime.now().isoformat(),
                                            description=title[:100] if title else "",
                                            source=platform_name,
                                            controversy_score=self.controversy_analyzer.calculate_controversy_score(title),
                                            engagement_potential=0.7  # 国内平台默认互动潜力
                                        )
                                        news_items.append(news_item)

                            if news_items:  # 只有当有有效数据时才返回
                                platform_news = PlatformNews(
                                    platform=platform_name,
                                    news_list=news_items,
                                    update_time=datetime.now().isoformat(),
                                    total_count=len(news_items),
                                    platform_type="domestic"
                                )

                                # 缓存结果
                                cache_key = f"news_{platform}_{limit}"
                                self.cache_manager.set(cache_key, platform_news)
                                logger.info(f"✅ {platform_name} 数据获取成功: {len(news_items)}条")
                                return platform_news
                            else:
                                logger.warning(f"vvhan API返回空数据 - 平台: {platform_name}")
                                return await self._get_mock_news(platform, limit)
                        else:
                            # API返回失败或格式不正确
                            success_status = data.get("success")
                            message = data.get("message", "未知错误")
                            logger.warning(f"vvhan API返回失败 - 平台: {platform_name}, success: {success_status}, message: {message}")
                            return await self._get_mock_news(platform, limit)
                    else:
                        logger.warning(f"vvhan API请求失败 - 平台: {platform_name}, 状态码: {response.status_code}")
                        return await self._get_mock_news(platform, limit)
                        
                except Exception as e:
                    logger.error(f"获取 {platform_name} 数据时发生异常: {str(e)}")
                    return await self._get_mock_news(platform, limit)
        
        return await self._get_mock_news(platform, limit)

    async def _get_global_platform_news(self, platform: str, limit: int) -> Optional[PlatformNews]:
        """获取全球平台新闻"""
        platform_info = self.global_platforms[platform]
        platform_type = platform_info["type"]
        
        if platform_type == "serpapi":
            return await self._get_google_trends_data(limit)
        elif platform_type == "newsapi":
            return await self._get_news_api_data(limit)
        elif platform_type == "reddit":
            return await self._get_reddit_data(limit)
        elif platform_type == "twitter":
            return await self._get_twitter_data(limit)
        else:
            return await self._get_mock_news(platform, limit)

    async def _get_google_trends_data(self, limit: int) -> Optional[PlatformNews]:
        """获取Google Trends数据"""
        try:
            serpapi_key = self.config.serpapi_key
            if not serpapi_key:
                logger.warning("SERPAPI_KEY未配置，跳过Google Trends数据获取")
                return await self._get_mock_news("google_trends", limit)
            
            # Google Trends Trending Now API通过SerpAPI
            url = "https://serpapi.com/search"
            params = {
                "engine": "google_trends_trending_now",
                "geo": "US",  # 使用正确的geo参数
                "hl": "en",   # 语言
                "api_key": serpapi_key
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    news_items = []
                    
                    # 解析Google Trends数据
                    trending_searches = data.get("trending_searches", [])
                    if trending_searches:
                        for i, item in enumerate(trending_searches[:limit]):
                            query = item.get("query", "")
                            if query:
                                news_item = NewsItem(
                                    title=query,
                                    url=f"https://trends.google.com/trends/explore?q={query}",
                                    hot_value=item.get('search_volume', 'N/A'),
                                    rank=i + 1,
                                    platform="Google Trends",
                                    timestamp=datetime.now().isoformat(),
                                    description=f"Google搜索热度: {item.get('search_volume', 'N/A')}",
                                    source="Google Trends",
                                    controversy_score=self.controversy_analyzer.calculate_controversy_score(query),
                                    engagement_potential=0.8  # Google趋势通常有高互动潜力
                                )
                                news_items.append(news_item)
                    
                    platform_news = PlatformNews(
                        platform="Google Trends",
                        news_list=news_items,
                        update_time=datetime.now().isoformat(),
                        total_count=len(news_items),
                        platform_type="global"
                    )
                    
                    cache_key = f"news_google_trends_{limit}"
                    self.cache_manager.set(cache_key, platform_news)
                    logger.info(f"✅ Google Trends 数据获取成功: {len(news_items)}条")
                    return platform_news
                else:
                    logger.warning(f"Google Trends API请求失败: {response.status_code}")
                    return await self._get_mock_news("google_trends", limit)
                    
        except Exception as e:
            logger.error(f"获取Google Trends数据失败: {e}")
            return await self._get_mock_news("google_trends", limit)

    async def _get_news_api_data(self, limit: int) -> Optional[PlatformNews]:
        """获取NewsAPI数据"""
        try:
            newsapi_key = self.config.newsapi_key
            if not newsapi_key:
                logger.warning("NEWSAPI_KEY未配置，跳过NewsAPI数据获取")
                return await self._get_mock_news("news_api", limit)
            
            # NewsAPI热门新闻
            url = "https://newsapi.org/v2/top-headlines"
            params = {
                "category": "general",
                "pageSize": min(limit, 20),  # NewsAPI限制
                "apiKey": newsapi_key,
                "language": "en"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    news_items = []
                    
                    # 解析新闻数据
                    articles = data.get("articles", [])
                    for i, article in enumerate(articles):
                        title = article.get("title", "")
                        if title and title != "[Removed]" and len(title) > 10:
                            news_item = NewsItem(
                                title=title,
                                url=article.get("url", ""),
                                hot_value="N/A",
                                rank=i + 1,
                                platform="NewsAPI",
                                timestamp=datetime.now().isoformat(),
                                description=article.get("description", "")[:100] if article.get("description") else "",
                                source=f"NewsAPI - {article.get('source', {}).get('name', 'Unknown')}",
                                controversy_score=self.controversy_analyzer.calculate_controversy_score(title),
                                engagement_potential=0.7  # 新闻通常有较高的互动潜力
                            )
                            news_items.append(news_item)
                    
                    platform_news = PlatformNews(
                        platform="NewsAPI",
                        news_list=news_items,
                        update_time=datetime.now().isoformat(),
                        total_count=len(news_items),
                        platform_type="global"
                    )
                    
                    cache_key = f"news_news_api_{limit}"
                    self.cache_manager.set(cache_key, platform_news)
                    logger.info(f"✅ NewsAPI 数据获取成功: {len(news_items)}条")
                    return platform_news
                else:
                    logger.warning(f"NewsAPI请求失败: {response.status_code}")
                    return await self._get_mock_news("news_api", limit)
                    
        except Exception as e:
            logger.error(f"获取NewsAPI数据失败: {e}")
            return await self._get_mock_news("news_api", limit)

    async def _get_reddit_data(self, limit: int) -> Optional[PlatformNews]:
        """获取Reddit数据"""
        try:
            client_id = self.config.reddit_client_id
            client_secret = self.config.reddit_client_secret
            user_agent = self.config.reddit_user_agent
            
            if not self.config.has_reddit():
                logger.warning("Reddit API配置不完整，跳过Reddit数据获取")
                return await self._get_mock_news("reddit", limit)
            
            # Reddit OAuth认证
            auth_url = "https://www.reddit.com/api/v1/access_token"
            auth_data = {"grant_type": "client_credentials"}
            
            credentials = f"{client_id}:{client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "User-Agent": user_agent
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 获取访问令牌
                response = await client.post(auth_url, data=auth_data, headers=headers)
                if response.status_code == 200:
                    token_data = response.json()
                    access_token = token_data.get("access_token")
                    
                    if access_token:
                        # 获取热门帖子
                        api_headers = {
                            "Authorization": f"Bearer {access_token}",
                            "User-Agent": user_agent
                        }
                        
                        news_items = []
                        subreddits = ["popular", "worldnews"]
                        
                        for subreddit in subreddits:
                            reddit_url = f"https://oauth.reddit.com/r/{subreddit}/hot"
                            params = {"limit": min(limit // len(subreddits), 10)}
                            
                            reddit_response = await client.get(reddit_url, headers=api_headers, params=params)
                            if reddit_response.status_code == 200:
                                reddit_data = reddit_response.json()
                                
                                for post in reddit_data.get("data", {}).get("children", []):
                                    post_data = post.get("data", {})
                                    title = post_data.get("title", "")
                                    
                                    if title and len(title) > 10:
                                        news_item = NewsItem(
                                            title=title,
                                            url=f"https://reddit.com{post_data.get('permalink', '')}",
                                            hot_value=post_data.get('score', 0),
                                            rank=len(news_items) + 1,
                                            platform="Reddit",
                                            timestamp=datetime.now().isoformat(),
                                            description=f"Reddit r/{subreddit} - {post_data.get('score', 0)} upvotes",
                                            source=f"Reddit r/{subreddit}",
                                            controversy_score=self.controversy_analyzer.calculate_controversy_score(title),
                                            engagement_potential=min(post_data.get('score', 0) / 1000.0, 1.0)
                                        )
                                        news_items.append(news_item)
                        
                        platform_news = PlatformNews(
                            platform="Reddit",
                            news_list=news_items[:limit],
                            update_time=datetime.now().isoformat(),
                            total_count=len(news_items[:limit]),
                            platform_type="global"
                        )
                        
                        cache_key = f"news_reddit_{limit}"
                        self.cache_manager.set(cache_key, platform_news)
                        logger.info(f"✅ Reddit 数据获取成功: {len(news_items[:limit])}条")
                        return platform_news
                
                logger.warning(f"Reddit认证失败: {response.status_code}")
                return await self._get_mock_news("reddit", limit)
                
        except Exception as e:
            logger.error(f"获取Reddit数据失败: {e}")
            return await self._get_mock_news("reddit", limit)

    async def _get_twitter_data(self, limit: int) -> Optional[PlatformNews]:
        """获取Twitter数据"""
        try:
            # 尝试使用第三方Twitter API服务
            twitterapi_key = self.config.twitter_api_io_token
            zyla_key = self.config.zyla_api_key
            
            if twitterapi_key:
                return await self._get_twitter_via_twitterapi_io(twitterapi_key, limit)
            elif zyla_key:
                return await self._get_twitter_via_zyla(zyla_key, limit)
            else:
                logger.warning("Twitter API配置不完整，跳过Twitter数据获取")
                return await self._get_mock_news("twitter", limit)
                
        except Exception as e:
            logger.error(f"获取Twitter数据失败: {e}")
            return await self._get_mock_news("twitter", limit)

    async def _get_twitter_via_twitterapi_io(self, api_key: str, limit: int) -> Optional[PlatformNews]:
        """通过TwitterAPI.io获取Twitter趋势"""
        try:
            url = "https://api.twitterapi.io/twitter/trend/trending"
            headers = {"X-API-Key": api_key}
            params = {"woeid": "1"}  # 全球趋势
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    news_items = []
                    
                    for i, trend in enumerate(data.get("trends", [])[:limit]):
                        title = trend.get("name", "")
                        if title:
                            news_item = NewsItem(
                                title=title,
                                url=trend.get("url", ""),
                                hot_value=trend.get('tweet_volume', 0),
                                rank=i + 1,
                                platform="Twitter",
                                timestamp=datetime.now().isoformat(),
                                description=f"Twitter趋势 - {trend.get('tweet_volume', 0)} tweets",
                                source="Twitter (TwitterAPI.io)",
                                controversy_score=self.controversy_analyzer.calculate_controversy_score(title),
                                engagement_potential=min((trend.get('tweet_volume', 0) or 0) / 10000.0, 1.0)
                            )
                            news_items.append(news_item)
                    
                    platform_news = PlatformNews(
                        platform="Twitter",
                        news_list=news_items,
                        update_time=datetime.now().isoformat(),
                        total_count=len(news_items),
                        platform_type="global"
                    )
                    
                    cache_key = f"news_twitter_{limit}"
                    self.cache_manager.set(cache_key, platform_news)
                    logger.info(f"✅ Twitter 数据获取成功: {len(news_items)}条")
                    return platform_news
                else:
                    logger.warning(f"TwitterAPI.io请求失败: {response.status_code}")
                    return await self._get_mock_news("twitter", limit)
                    
        except Exception as e:
            logger.error(f"TwitterAPI.io获取数据失败: {e}")
            return await self._get_mock_news("twitter", limit)

    async def _get_twitter_via_zyla(self, api_key: str, limit: int) -> Optional[PlatformNews]:
        """通过Zyla API获取Twitter趋势"""
        try:
            url = "https://zylalabs.com/api/1858/twitter+x+trends+api/5930/trends+capture"
            headers = {"Authorization": f"Bearer {api_key}"}
            params = {"woeid": "1"}  # 全球趋势
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    news_items = []
                    
                    for i, trend in enumerate(data.get("trends", [])[:limit]):
                        title = trend.get("name", "")
                        if title:
                            news_item = NewsItem(
                                title=title,
                                url=trend.get("url", ""),
                                hot_value="N/A",
                                rank=i + 1,
                                platform="Twitter",
                                timestamp=datetime.now().isoformat(),
                                description=f"Twitter趋势 - {trend.get('tweet_volume_text', '未知')} tweets",
                                source="Twitter (Zyla API)",
                                controversy_score=self.controversy_analyzer.calculate_controversy_score(title),
                                engagement_potential=0.8  # Twitter趋势通常有高互动潜力
                            )
                            news_items.append(news_item)
                    
                    platform_news = PlatformNews(
                        platform="Twitter",
                        news_list=news_items,
                        update_time=datetime.now().isoformat(),
                        total_count=len(news_items),
                        platform_type="global"
                    )
                    
                    cache_key = f"news_twitter_{limit}"
                    self.cache_manager.set(cache_key, platform_news)
                    logger.info(f"✅ Twitter 数据获取成功: {len(news_items)}条")
                    return platform_news
                else:
                    logger.warning(f"Zyla API请求失败: {response.status_code}")
                    return await self._get_mock_news("twitter", limit)
                    
        except Exception as e:
            logger.error(f"Zyla API获取数据失败: {e}")
            return await self._get_mock_news("twitter", limit)

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

    async def get_domestic_platforms_news(self, limit: int = 10) -> List[PlatformNews]:
        """获取国内平台热点新闻"""
        all_news = []

        tasks = [
            self.get_platform_news(platform, limit)
            for platform in self.domestic_platforms.keys()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, PlatformNews):
                all_news.append(result)
            elif isinstance(result, Exception):
                logger.error(f"获取国内平台新闻失败: {result}")

        return all_news

    async def get_global_platforms_news(self, limit: int = 10) -> List[PlatformNews]:
        """获取全球平台热点新闻"""
        all_news = []

        tasks = [
            self.get_platform_news(platform, limit)
            for platform in self.global_platforms.keys()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, PlatformNews):
                all_news.append(result)
            elif isinstance(result, Exception):
                logger.error(f"获取全球平台新闻失败: {result}")

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
            "ithome": ["IT之家", "科技新闻", "数码产品", "软件更新", "行业动态"],
            "google_trends": ["Google热搜", "全球趋势", "搜索热词", "流行话题", "国际关注"],
            "news_api": ["国际新闻", "全球资讯", "突发事件", "政治经济", "科技创新"],
            "reddit": ["Reddit热帖", "社区讨论", "国际话题", "技术分享", "文化交流"],
            "twitter": ["Twitter趋势", "全球热议", "实时话题", "社交媒体", "国际动态"],
        }

        titles = base_titles.get(platform, ["热门话题", "流行内容", "用户关注", "热点讨论", "趋势话题"])

        # 生成模拟新闻条目
        news_items = []
        for i in range(min(limit, len(titles))):
            title = f"{titles[i % len(titles)]} {i+1}"
            news_item = NewsItem(
                title=title,
                url=f"https://example.com/{platform}/{i+1}",
                hot_value=1000 - i * 50,
                rank=i + 1,
                platform=platform_name,
                timestamp=datetime.now().isoformat(),
                description=f"这是{platform_name}的模拟热点内容",
                source=f"{platform_name} (模拟数据)",
                controversy_score=self.controversy_analyzer.calculate_controversy_score(title),
                engagement_potential=0.5  # 模拟数据默认互动潜力
            )
            news_items.append(news_item)

        # 确定平台类型
        platform_type = "global" if platform in self.global_platforms else "domestic"

        return PlatformNews(
            platform=platform_name,
            news_list=news_items,
            update_time=datetime.now().isoformat(),
            total_count=len(news_items),
            platform_type=platform_type
        )

    def analyze_trends(self, all_news: List[PlatformNews]) -> TrendAnalysis:
        """分析热点趋势"""
        hot_keywords = []
        trending_topics = []
        platform_summary = {}
        controversy_scores = []

        for platform_news in all_news:
            platform_summary[platform_news.platform] = platform_news.total_count
            
            for news_item in platform_news.news_list:
                # 提取关键词（简单实现）
                title_words = news_item.title.split()
                hot_keywords.extend([word for word in title_words if len(word) > 2])
                
                # 添加趋势话题
                trending_topics.append(news_item.title)
                
                # 收集争议性分数
                if news_item.controversy_score:
                    controversy_scores.append(news_item.controversy_score)

        # 统计最热门的关键词
        from collections import Counter
        keyword_counts = Counter(hot_keywords)
        hot_keywords = [word for word, count in keyword_counts.most_common(10)]
        
        # 争议性分析
        controversy_analysis = {
            "average_controversy": sum(controversy_scores) / len(controversy_scores) if controversy_scores else 0,
            "high_controversy_count": len([s for s in controversy_scores if s > 0.7]),
            "medium_controversy_count": len([s for s in controversy_scores if 0.3 < s <= 0.7]),
            "low_controversy_count": len([s for s in controversy_scores if s <= 0.3]),
        }

        return TrendAnalysis(
            hot_keywords=hot_keywords,
            trending_topics=trending_topics[:20],  # 取前20个话题
            platform_summary=platform_summary,
            analysis_time=datetime.now().isoformat(),
            controversy_analysis=controversy_analysis
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
    platform: str = Field(description="平台名称，如 weibo, zhihu, baidu, google_trends, news_api, reddit, twitter 等"),
    limit: int = Field(default=20, description="获取新闻数量，默认20条"),
) -> str:
    """获取指定平台的热点新闻"""
    try:
        platform_news = await news_provider.get_platform_news(platform, limit)
        if platform_news:
            return json.dumps(
                platform_news.model_dump(), ensure_ascii=False, indent=2
            )
        else:
            return json.dumps(
                {"error": f"无法获取平台 {platform} 的新闻数据"}, ensure_ascii=False
            )
    except Exception as e:
        logger.error(f"获取热点新闻时出错: {str(e)}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def get_all_platforms_news(
    limit: int = Field(default=10, description="每个平台获取新闻数量，默认10条")
) -> str:
    """获取所有平台（国内+全球）热点新闻"""
    try:
        all_news = await news_provider.get_all_platforms_news(limit)
        
        result = {
            "platforms": [news.model_dump() for news in all_news],
            "total_platforms": len(all_news),
            "update_time": datetime.now().isoformat(),
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取所有平台新闻时出错: {str(e)}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def get_domestic_platforms_news(
    limit: int = Field(default=10, description="每个平台获取新闻数量，默认10条")
) -> str:
    """获取国内平台热点新闻"""
    try:
        domestic_news = await news_provider.get_domestic_platforms_news(limit)
        
        result = {
            "platforms": [news.model_dump() for news in domestic_news],
            "total_platforms": len(domestic_news),
            "platform_type": "domestic",
            "update_time": datetime.now().isoformat(),
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取国内平台新闻时出错: {str(e)}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def get_global_platforms_news(
    limit: int = Field(default=10, description="每个平台获取新闻数量，默认10条")
) -> str:
    """获取全球平台热点新闻"""
    try:
        global_news = await news_provider.get_global_platforms_news(limit)
        
        result = {
            "platforms": [news.model_dump() for news in global_news],
            "total_platforms": len(global_news),
            "platform_type": "global",
            "update_time": datetime.now().isoformat(),
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取全球平台新闻时出错: {str(e)}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def analyze_trends(
    limit: int = Field(default=10, description="每个平台分析新闻数量，默认10条")
) -> str:
    """分析热点趋势"""
    try:
        all_news = await news_provider.get_all_platforms_news(limit)
        analysis = news_provider.analyze_trends(all_news)
        
        return json.dumps(analysis.model_dump(), ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"分析趋势时出错: {str(e)}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def analyze_controversy_trends(
    limit: int = Field(default=10, description="每个平台分析新闻数量，默认10条")
) -> str:
    """分析争议性趋势"""
    try:
        all_news = await news_provider.get_all_platforms_news(limit)
        
        # 收集所有新闻项目并按争议性排序
        all_items = []
        for platform_news in all_news:
            for item in platform_news.news_list:
                all_items.append({
                    "title": item.title,
                    "platform": item.platform,
                    "controversy_score": item.controversy_score,
                    "engagement_potential": item.engagement_potential,
                    "url": item.url
                })
        
        # 按争议性分数排序
        all_items.sort(key=lambda x: x["controversy_score"], reverse=True)
        
        result = {
            "high_controversy_items": all_items[:10],  # 前10个最具争议性的
            "total_analyzed": len(all_items),
            "average_controversy": sum(item["controversy_score"] for item in all_items) / len(all_items) if all_items else 0,
            "analysis_time": datetime.now().isoformat()
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"分析争议性趋势时出错: {str(e)}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def get_server_health() -> str:
    """获取服务器健康状态"""
    try:
        cache_stats = news_provider.cache_manager.get_stats()
        
        health_info = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "cache_stats": cache_stats,
            "supported_platforms": {
                "domestic": list(news_provider.domestic_platforms.keys()),
                "global": list(news_provider.global_platforms.keys()),
                "total": len(news_provider.platforms)
            },
            "api_status": {
                "serpapi_configured": bool(os.getenv('SERPAPI_KEY')),
                "newsapi_configured": bool(os.getenv('NEWSAPI_KEY')),
                "reddit_configured": bool(os.getenv('REDDIT_CLIENT_ID') and os.getenv('REDDIT_CLIENT_SECRET')),
                "twitter_configured": bool(os.getenv('TWITTERAPI_IO_KEY') or os.getenv('ZYLA_API_KEY'))
            }
        }
        
        return json.dumps(health_info, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取服务器健康状态时出错: {str(e)}")
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def clear_cache() -> str:
    """清空缓存"""
    try:
        news_provider.cache_manager.clear()
        return json.dumps(
            {
                "status": "success",
                "message": "缓存已清空",
                "timestamp": datetime.now().isoformat(),
            },
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"清空缓存时出错: {str(e)}")
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)


# ================== 资源定义 ==================


@mcp.resource("hot-news://platforms")
def get_supported_platforms() -> str:
    """获取支持的平台列表"""
    platforms_info = {
        "domestic_platforms": {
            platform: info["name"] for platform, info in news_provider.domestic_platforms.items()
        },
        "global_platforms": {
            platform: info["name"] for platform, info in news_provider.global_platforms.items()
        },
        "total_count": len(news_provider.platforms)
    }
    return json.dumps(platforms_info, ensure_ascii=False, indent=2)


@mcp.resource("hot-news://config")
def get_server_config() -> str:
    """获取服务器配置信息"""
    config_info = {
        "server_name": "HotNewsServer",
        "version": "2.0.0",
        "description": "支持国内和全球平台的热点新闻聚合服务",
        "features": [
            "多平台热点新闻聚合",
            "智能缓存管理",
            "趋势分析",
            "争议性分析",
            "国内外平台分类",
            "实时数据获取"
        ],
        "supported_apis": [
            "vvhan API (国内平台)",
            "Google Trends (SerpAPI)",
            "NewsAPI",
            "Reddit API",
            "Twitter API (第三方)"
        ]
    }
    return json.dumps(config_info, ensure_ascii=False, indent=2)


# ================== 主程序入口 ==================


def main():
    """启动MCP服务器"""
    logger.info("🚀 启动热点新闻MCP服务器...")
    logger.info(f"📊 支持平台数量: {len(news_provider.platforms)}")
    logger.info(f"🏠 国内平台: {list(news_provider.domestic_platforms.keys())}")
    logger.info(f"🌍 全球平台: {list(news_provider.global_platforms.keys())}")
    
    # 检查API配置
    api_status = []
    if os.getenv('SERPAPI_KEY'):
        api_status.append("✅ Google Trends (SerpAPI)")
    else:
        api_status.append("❌ Google Trends (SerpAPI) - 未配置SERPAPI_KEY")
    
    if os.getenv('NEWSAPI_KEY'):
        api_status.append("✅ NewsAPI")
    else:
        api_status.append("❌ NewsAPI - 未配置NEWSAPI_KEY")
    
    if os.getenv('REDDIT_CLIENT_ID') and os.getenv('REDDIT_CLIENT_SECRET'):
        api_status.append("✅ Reddit API")
    else:
        api_status.append("❌ Reddit API - 未配置Reddit凭据")
    
    if os.getenv('TWITTERAPI_IO_KEY') or os.getenv('ZYLA_API_KEY'):
        api_status.append("✅ Twitter API")
    else:
        api_status.append("❌ Twitter API - 未配置Twitter API密钥")
    
    logger.info("🔧 API配置状态:")
    for status in api_status:
        logger.info(f"   {status}")
    
    mcp.run()


if __name__ == "__main__":
    main()
