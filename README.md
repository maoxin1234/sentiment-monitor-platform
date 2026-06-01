# 舆情实时监控与大模型智能分析平台

> 基于 Kafka + Flink 流处理架构，集成本地/云端大模型协同分析，提供实时可视化大屏与智能告警的开源舆情监控平台。

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| **实时流处理** | 模拟 Kafka 数据源 + Flink 滑动窗口（10s/60s），QPS 毫秒级统计 |
| **多模型协同** | 本地模型（DeepSeek/Qwen via Ollama）+ 云端模型混合调度，支持 local_first / cost_aware / load_balance 策略 |
| **可视化大屏** | 地域热力图、话题关联力导向图谱、情感时序、QPS 趋势，WebSocket 实时推送 |
| **智能告警** | 4 种规则检测（流量激增/情感骤降/负面率/话题负面），支持飞书/钉钉/企业微信 Webhook |
| **多平台覆盖** | 微博、小红书、抖音、B 站、知乎、Twitter、微信 |

## 🏗️ 系统架构

```
社交媒体数据源（Kafka / 模拟流）
        │
        ▼
 Flink Stream Processor
  ├── 10s 滚动窗口（QPS / 情感分布）
  ├── 60s 滑动窗口（情感均值 / 趋势）
  └── KeyBy(话题) 聚合 → TopN
        │
        ▼
 LLM Router（多模型协同）
  ├── 本地优先：Ollama → DeepSeek-R1:7B / Qwen
  └── 降级：云端 API（DeepSeek / OpenAI 兼容）
        │
        ▼
 异常检测 → 告警推送（WebSocket / Webhook）
        │
        ▼
 FastAPI + WebSocket → 前端大屏（Vue3 + ECharts5）
```

## 🚀 快速启动

### 方式一：模拟模式（无需任何依赖）

```powershell
# Windows PowerShell
.\start.ps1
```

访问 http://localhost:8001

### 方式二：接入真实 LLM

```powershell
$env:CLOUD_API_KEY = "sk-your-deepseek-key"
$env:CLOUD_LLM_URL = "https://api.deepseek.com/v1"
$env:CLOUD_MODEL   = "deepseek-chat"
$env:LLM_ROUTING   = "local_first"   # 或 cost_aware / cloud_first
.\start.ps1
```

### 方式三：完整生产环境（Docker）

```bash
# 包含 Kafka + Zookeeper + Redis + Ollama
CLOUD_API_KEY=sk-xxx docker-compose up -d

# 拉取本地模型
docker exec ollama ollama pull deepseek-r1:7b
```

## 📊 功能截图

大屏包含：
- **顶部**：实时采集量、QPS、活跃告警数、模型分配比例、WebSocket 状态
- **告警横幅**：流量激增 / 话题负面 / 情感骤降告警，可一键确认
- **左列**：情感分布饼图、平台来源柱图、大模型调度仪表盘
- **中列**：地域舆情热力图（中国地图）、话题关联图谱（实时力导向）
- **右列**：Flink 窗口 QPS 趋势、情感指数趋势、实时帖子数据流

## ⚙️ 配置项

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `USE_MOCK` | `true` | 是否使用模拟数据流 |
| `MOCK_RATE` | `5` | 模拟数据生成速率（条/秒） |
| `LOCAL_LLM_URL` | `http://localhost:11434/v1` | 本地 Ollama 地址 |
| `LOCAL_MODEL` | `deepseek-r1:7b` | 本地模型名称 |
| `CLOUD_API_KEY` | `` | 云端模型 API Key |
| `CLOUD_LLM_URL` | `https://api.deepseek.com/v1` | 云端 API 地址 |
| `LLM_ROUTING` | `local_first` | 路由策略 |
| `ALERT_WEBHOOK` | `` | 飞书/钉钉 Webhook URL |
| `KAFKA_SERVERS` | `localhost:9092` | Kafka 地址 |

## 📁 项目结构

```
sentiment-platform/
├── backend/
│   ├── main.py                    # FastAPI 主入口 + WebSocket
│   ├── config.py                  # 全局配置
│   ├── stream/
│   │   ├── mock_producer.py       # 模拟 Kafka 数据源
│   │   └── flink_processor.py     # 滑动窗口算子
│   ├── analysis/
│   │   ├── llm_router.py          # 多模型路由器
│   │   └── sentiment_analyzer.py  # 情感分析引擎
│   ├── alert/
│   │   ├── detector.py            # 异常检测规则
│   │   └── notifier.py            # 多渠道推送
│   ├── models/schemas.py          # Pydantic 数据模型
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html                 # 大屏主页
│   ├── css/style.css              # 暗色主题样式
│   └── js/app.js                  # Vue3 + ECharts 逻辑
├── docker-compose.yml
├── start.ps1                      # Windows 快速启动
└── README.md
```

## 🔧 扩展指南

**接入真实 Kafka**：替换 `stream/mock_producer.py` 中的 `generate_post_stream` 为 `aiokafka.AIOKafkaConsumer`。

**接入真实 Flink**：`stream/flink_processor.py` 中的窗口逻辑可直接迁移至 PyFlink DataStream API。

**添加新平台**：在 `models/schemas.py` 的 `Platform` 枚举中添加新平台，在爬虫层对接相应 API。

## 📜 License

MIT
