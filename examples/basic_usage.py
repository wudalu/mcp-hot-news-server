#!/usr/bin/env python3
"""
MCP Hot News Server - 基础使用示例
Basic Usage Example
"""

import asyncio
import json
from mcp_hot_news.client import HotNewsClient

async def main():
    """基础使用示例"""
    print("🚀 MCP Hot News Server 基础使用示例")
    print("=" * 50)
    
    async with HotNewsClient() as client:
        # 1. 获取服务器健康状态
        print("\n📊 服务器健康状态:")
        health = await client.get_server_health()
        print(json.dumps(json.loads(health), indent=2, ensure_ascii=False))
        
        # 2. 获取知乎热榜
        print("\n🔥 知乎热榜 (前5条):")
        zhihu_news = await client.get_hot_news("zhihu", limit=5)
        zhihu_data = json.loads(zhihu_news)
        for i, news in enumerate(zhihu_data["news_list"][:3], 1):
            print(f"{i}. {news['title']}")
        
        # 3. 获取抖音热点
        print("\n🎵 抖音热点 (前3条):")
        douyin_news = await client.get_hot_news("douyin", limit=3)
        douyin_data = json.loads(douyin_news)
        for i, news in enumerate(douyin_data["news_list"], 1):
            print(f"{i}. {news['title']}")
        
        # 4. 分析热点趋势
        print("\n📈 热点趋势分析:")
        trends = await client.analyze_trends(limit=5)
        trends_data = json.loads(trends)
        print(f"热门关键词: {', '.join(trends_data['hot_keywords'][:10])}")
        print(f"平台统计: {trends_data['platform_summary']}")

if __name__ == "__main__":
    asyncio.run(main()) 