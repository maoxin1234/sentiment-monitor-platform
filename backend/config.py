import os
from dataclasses import dataclass, field

@dataclass
class KafkaConfig:
    bootstrap_servers: str = os.getenv("KAFKA_SERVERS", "localhost:9092")
    topic_raw: str = "social_raw"
    topic_analyzed: str = "social_analyzed"
    topic_alert: str = "social_alert"
    group_id: str = "sentiment_group"

@dataclass
class LLMConfig:
    # 本地模型配置（Ollama兼容接口）
    local_base_url: str = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/v1")
    local_model: str = os.getenv("LOCAL_MODEL", "deepseek-r1:7b")
    local_api_key: str = "ollama"

    # 云端模型配置（OpenAI兼容接口）
    cloud_base_url: str = os.getenv("CLOUD_LLM_URL", "https://api.deepseek.com/v1")
    cloud_model: str = os.getenv("CLOUD_MODEL", "deepseek-chat")
    cloud_api_key: str = os.getenv("CLOUD_API_KEY", "")

    # 路由策略: "local_first" | "cloud_first" | "load_balance" | "cost_aware"
    routing_strategy: str = os.getenv("LLM_ROUTING", "local_first")
    # 本地模型处理复杂度阈值（超过则转云端）
    complexity_threshold: float = 0.7
    # 最大并发请求数
    max_concurrent_local: int = 3
    max_concurrent_cloud: int = 10

@dataclass
class AlertConfig:
    # 告警阈值
    negative_rate_threshold: float = 0.6     # 负面率超过60%触发
    volume_spike_threshold: float = 3.0      # 流量是基线的3倍触发
    sentiment_drop_threshold: float = -0.3   # 情感值骤降超过0.3触发
    # 推送渠道
    webhook_url: str = os.getenv("ALERT_WEBHOOK", "")
    email_smtp: str = os.getenv("SMTP_SERVER", "")
    # 告警冷却时间（秒）
    cooldown_seconds: int = 300

@dataclass
class AppConfig:
    kafka: KafkaConfig = field(default_factory=KafkaConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    alert: AlertConfig = field(default_factory=AlertConfig)
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    # 是否使用模拟数据（无真实Kafka时启用）
    use_mock_stream: bool = os.getenv("USE_MOCK", "true").lower() == "true"
    # 模拟数据生成速率（条/秒）
    mock_rate: float = float(os.getenv("MOCK_RATE", "5"))
    ws_heartbeat: int = 30

config = AppConfig()
