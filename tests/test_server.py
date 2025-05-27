#!/usr/bin/env python3
"""
MCP热点新闻服务器测试
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime

# 导入测试模块
from mcp_hot_news.server import (
    HotNewsProvider,
    CacheManager,
    NewsItem,
    PlatformNews,
    get_hot_news,
    get_all_platforms_news,
    analyze_trends,
    get_server_health,
    clear_cache,
)


class TestCacheManager:
    """缓存管理器测试"""

    def test_cache_basic_operations(self):
        """测试基本缓存操作"""
        cache = CacheManager()

        # 测试设置和获取
        cache.set("test_key", {"data": "test_value"})
        result = cache.get("test_key")
        assert result == {"data": "test_value"}

        # 测试不存在的键
        assert cache.get("non_existent_key") is None

        # 测试清空缓存
        cache.clear()
        assert cache.get("test_key") is None

    def test_cache_stats(self):
        """测试缓存统计"""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        stats = cache.get_stats()
        assert stats["total_items"] == 2
        assert stats["valid_items"] == 2
        assert stats["cache_hit_ratio"] == 1.0


class TestDataModels:
    """数据模型测试"""

    def test_news_item_model(self):
        """测试新闻条目模型"""
        news_item = NewsItem(
            title="测试新闻",
            url="https://example.com",
            hot_value=100,
            rank=1,
            platform="测试平台",
            timestamp=datetime.now().isoformat(),
        )

        assert news_item.title == "测试新闻"
        assert news_item.platform == "测试平台"
        assert news_item.rank == 1

    def test_platform_news_model(self):
        """测试平台新闻模型"""
        news_items = [
            NewsItem(
                title=f"新闻{i}",
                url=f"https://example.com/{i}",
                rank=i,
                platform="测试平台",
                timestamp=datetime.now().isoformat(),
            )
            for i in range(1, 4)
        ]

        platform_news = PlatformNews(
            platform="测试平台",
            news_list=news_items,
            update_time=datetime.now().isoformat(),
            total_count=len(news_items),
        )

        assert platform_news.platform == "测试平台"
        assert platform_news.total_count == 3
        assert len(platform_news.news_list) == 3


class TestHotNewsProvider:
    """热点新闻提供者测试"""

    def test_provider_initialization(self):
        """测试提供者初始化"""
        provider = HotNewsProvider()

        assert provider.cache_manager is not None
        assert provider.vvhan_base_url == "https://api.vvhan.com/api/hotlist"
        assert len(provider.platforms) > 0
        assert "weibo" in provider.platforms
        assert "zhihu" in provider.platforms

    @pytest.mark.asyncio
    async def test_get_platform_news_invalid_platform(self):
        """测试获取不支持平台的新闻"""
        provider = HotNewsProvider()
        result = await provider.get_platform_news("invalid_platform")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_platform_news_with_mock(self):
        """测试获取平台新闻（使用模拟数据）"""
        provider = HotNewsProvider()

        # 模拟API响应
        mock_response_data = {
            "success": True,
            "data": [
                {"title": "测试新闻1", "link": "https://example.com/1", "heat": 100},
                {"title": "测试新闻2", "link": "https://example.com/2", "heat": 90},
            ],
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_get.return_value = mock_response

            result = await provider.get_platform_news("weibo", limit=2)

            assert result is not None
            assert result.platform == "微博热搜"
            assert len(result.news_list) == 2
            assert result.news_list[0].title == "测试新闻1"


class TestMCPTools:
    """MCP工具函数测试"""

    @pytest.mark.asyncio
    async def test_get_hot_news_invalid_platform(self):
        """测试获取不支持平台的热点新闻"""
        result = await get_hot_news("invalid_platform")
        assert "不支持的平台" in result

    @pytest.mark.asyncio
    async def test_get_hot_news_invalid_limit(self):
        """测试无效的新闻数量限制"""
        result = await get_hot_news("weibo", limit=0)
        assert "新闻数量限制在1-50之间" in result

        result = await get_hot_news("weibo", limit=100)
        assert "新闻数量限制在1-50之间" in result

    @pytest.mark.asyncio
    async def test_get_all_platforms_news_invalid_limit(self):
        """测试获取所有平台新闻的无效限制"""
        result = await get_all_platforms_news(limit=0)
        assert "每平台新闻数量限制在1-20之间" in result

        result = await get_all_platforms_news(limit=30)
        assert "每平台新闻数量限制在1-20之间" in result

    @pytest.mark.asyncio
    async def test_analyze_trends_invalid_limit(self):
        """测试分析趋势的无效限制"""
        result = await analyze_trends(limit=0)
        assert "分析新闻数量限制在1-20之间" in result

        result = await analyze_trends(limit=30)
        assert "分析新闻数量限制在1-20之间" in result

    @pytest.mark.asyncio
    async def test_get_server_health(self):
        """测试获取服务器健康状态"""
        result = await get_server_health()

        # 解析JSON响应
        health_data = json.loads(result)

        assert health_data["status"] == "healthy"
        assert "timestamp" in health_data
        assert "supported_platforms" in health_data
        assert "cache_statistics" in health_data
        assert "version" in health_data
        assert len(health_data["supported_platforms"]) > 0

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        """测试清空缓存"""
        result = await clear_cache()

        # 解析JSON响应
        clear_data = json.loads(result)

        assert clear_data["status"] == "success"
        assert "缓存已清空" in clear_data["message"]
        assert "timestamp" in clear_data


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow_with_mock(self):
        """测试完整工作流程（使用模拟数据）"""
        # 1. 测试服务器健康状态
        health_result = await get_server_health()
        health_data = json.loads(health_result)
        assert health_data["status"] == "healthy"

        # 2. 清空缓存
        clear_result = await clear_cache()
        clear_data = json.loads(clear_result)
        assert clear_data["status"] == "success"

        # 3. 测试模拟获取新闻（由于网络依赖，这里主要测试错误处理）
        news_result = await get_hot_news("weibo", limit=5)
        # 由于是真实API调用，可能成功或失败，我们主要确保不会崩溃
        assert isinstance(news_result, str)

    def test_provider_platforms_configuration(self):
        """测试提供者平台配置"""
        provider = HotNewsProvider()

        # 检查必需的平台
        required_platforms = ["weibo", "zhihu", "baidu", "bilibili"]
        for platform in required_platforms:
            assert platform in provider.platforms
            platform_config = provider.platforms[platform]
            assert "name" in platform_config
            assert "api_path" in platform_config
            assert "vvhan" in platform_config


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
