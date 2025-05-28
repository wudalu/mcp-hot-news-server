"""
MCP Hot News Server 配置管理模块
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class MCPServerConfig:
    """MCP服务器配置管理"""
    
    def __init__(self):
        self._load_env_file()
        self._setup_logging()
    
    def _load_env_file(self):
        """加载.env文件"""
        # 查找.env文件的位置
        env_paths = [
            Path(__file__).parent.parent.parent / ".env",  # mcp-hot-news-server/.env
            Path(__file__).parent / ".env",                # src/mcp_hot_news/.env
            Path.cwd() / ".env"                           # 当前工作目录/.env
        ]
        
        env_file = None
        for path in env_paths:
            if path.exists():
                env_file = path
                logger.info(f"找到.env文件: {path}")
                break
        
        if env_file:
            self._parse_env_file(env_file)
        else:
            logger.warning("未找到.env文件，将使用系统环境变量")
    
    def _parse_env_file(self, env_file: Path):
        """解析.env文件"""
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        
                        # 只有当环境变量不存在时才设置
                        if key not in os.environ:
                            os.environ[key] = value
                            
            logger.info(f"成功加载.env文件: {env_file}")
        except Exception as e:
            logger.error(f"加载.env文件失败: {e}")
    
    def _setup_logging(self):
        """设置日志级别"""
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))
    
    # Google Trends (SerpAPI)
    @property
    def serpapi_key(self) -> Optional[str]:
        return os.getenv('SERPAPI_KEY')
    
    # NewsAPI
    @property
    def newsapi_key(self) -> Optional[str]:
        return os.getenv('NEWSAPI_KEY')
    
    # Reddit API
    @property
    def reddit_client_id(self) -> Optional[str]:
        return os.getenv('REDDIT_CLIENT_ID')
    
    @property
    def reddit_client_secret(self) -> Optional[str]:
        return os.getenv('REDDIT_CLIENT_SECRET')
    
    @property
    def reddit_user_agent(self) -> str:
        return os.getenv('REDDIT_USER_AGENT', 'MCP_Hot_News_Server/1.0')
    
    # Twitter APIs
    @property
    def twitter_api_io_token(self) -> Optional[str]:
        return os.getenv('TWITTER_API_IO_TOKEN')
    
    @property
    def zyla_api_key(self) -> Optional[str]:
        return os.getenv('ZYLA_API_KEY')
    
    @property
    def rapidapi_key(self) -> Optional[str]:
        return os.getenv('RAPIDAPI_KEY')
    
    def has_serpapi(self) -> bool:
        """检查是否有SerpAPI密钥"""
        return bool(self.serpapi_key)
    
    def has_newsapi(self) -> bool:
        """检查是否有NewsAPI密钥"""
        return bool(self.newsapi_key)
    
    def has_reddit(self) -> bool:
        """检查是否有Reddit API密钥"""
        return bool(self.reddit_client_id and self.reddit_client_secret)
    
    def has_twitter(self) -> bool:
        """检查是否有任何Twitter API密钥"""
        return bool(self.twitter_api_io_token or self.zyla_api_key or self.rapidapi_key)
    
    def get_available_apis(self) -> list[str]:
        """获取可用的API列表"""
        apis = []
        if self.has_newsapi():
            apis.append('newsapi')
        if self.has_serpapi():
            apis.append('serpapi')
        if self.has_reddit():
            apis.append('reddit')
        if self.has_twitter():
            apis.append('twitter')
        return apis
    
    def validate_config(self) -> tuple[bool, list[str]]:
        """验证配置是否有效"""
        issues = []
        
        if not self.has_newsapi():
            issues.append("缺少NewsAPI密钥 (NEWSAPI_KEY)")
        
        if not self.has_serpapi():
            issues.append("缺少SerpAPI密钥 (SERPAPI_KEY)")
        
        if not self.has_reddit():
            issues.append("缺少Reddit API密钥 (REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET)")
        
        if not self.has_twitter():
            issues.append("缺少Twitter API密钥 (TWITTER_API_IO_TOKEN, ZYLA_API_KEY, RAPIDAPI_KEY)")
        
        is_valid = len(issues) == 0
        return is_valid, issues

# 全局配置实例
mcp_config = MCPServerConfig() 