from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class Platform(str, Enum):
    weibo = "微博"
    xiaohongshu = "小红书"
    douyin = "抖音"
    bilibili = "B站"
    zhihu = "知乎"
    twitter = "Twitter"
    wechat = "微信"

class Sentiment(str, Enum):
    positive = "正面"
    neutral = "中性"
    negative = "负面"

class AlertLevel(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"

class RawPost(BaseModel):
    id: str
    platform: Platform
    content: str
    author: str
    region: Optional[str] = None          # 省份/城市，用于热力图
    likes: int = 0
    reposts: int = 0
    comments: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)
    topic_keywords: List[str] = []

class AnalyzedPost(BaseModel):
    raw: RawPost
    sentiment: Sentiment
    sentiment_score: float                 # -1.0 ~ 1.0
    emotion: str                           # 愤怒/喜悦/悲伤/恐惧/惊讶/中性
    topics: List[str] = []                 # 提取的话题标签
    summary: Optional[str] = None         # LLM生成的摘要
    heat_score: float = 0.0               # 热度分 = likes*1 + reposts*3 + comments*2
    processed_by: str = "local"           # "local" | "cloud"
    processing_ms: int = 0

class TopicNode(BaseModel):
    id: str
    label: str
    heat: float
    sentiment_avg: float
    post_count: int
    related: List[str] = []               # 关联话题id列表

class AlertEvent(BaseModel):
    id: str
    level: AlertLevel
    title: str
    description: str
    trigger_metric: str                    # 触发指标名
    current_value: float
    threshold: float
    topic: Optional[str] = None
    platform: Optional[Platform] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    acknowledged: bool = False

class RegionHeat(BaseModel):
    region: str
    province: str
    lat: float
    lng: float
    heat: float
    negative_rate: float
    post_count: int

class DashboardStats(BaseModel):
    total_posts_today: int
    posts_per_second: float
    sentiment_distribution: Dict[str, int]
    platform_distribution: Dict[str, int]
    top_topics: List[Dict[str, Any]]
    active_alerts: int
    llm_local_ratio: float                 # 本地模型处理占比
