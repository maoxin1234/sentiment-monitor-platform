"""
模拟 Flink 流处理算子
真实部署：使用 PyFlink 或通过 Flink REST API 提交 Job

实现的算子：
  - 时间窗口聚合（滚动窗口 10s / 滑动窗口 60s）
  - 基于热度的 TopN 话题
  - 情感趋势计算
  - 异常检测（流量突增 / 情感骤降）
"""
import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Callable, Awaitable
import time

logger = logging.getLogger(__name__)
from models.schemas import AnalyzedPost, Sentiment


class WindowBuffer:
    """滑动时间窗口缓冲区"""

    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self._buffer: deque = deque()

    def add(self, item: AnalyzedPost):
        now = time.time()
        self._buffer.append((now, item))
        self._evict()

    def _evict(self):
        cutoff = time.time() - self.window_seconds
        while self._buffer and self._buffer[0][0] < cutoff:
            self._buffer.popleft()

    def items(self) -> List[AnalyzedPost]:
        self._evict()
        return [item for _, item in self._buffer]

    def __len__(self):
        return len(self.items())


class FlinkStreamProcessor:
    """
    模拟 Flink DataStream 处理管道
    算子链: Source -> Map(enrich) -> KeyBy(topic) -> Window -> Aggregate -> Sink
    """

    def __init__(self):
        self._window_60s = WindowBuffer(60)
        self._window_10s = WindowBuffer(10)
        # 基线：用于异常检测（过去5分钟平均QPS）
        self._baseline_window = WindowBuffer(300)
        # 话题聚合：topic -> {count, sentiment_sum, heat_sum}
        self._topic_agg: Dict[str, dict] = defaultdict(
            lambda: {"count": 0, "sentiment_sum": 0.0, "heat_sum": 0.0, "related": set()}
        )
        # 地域热度聚合
        self._region_agg: Dict[str, dict] = defaultdict(
            lambda: {"count": 0, "heat_sum": 0.0, "negative_count": 0}
        )
        # 情感时序（用于骤降检测）
        self._sentiment_ts: deque = deque(maxlen=30)  # 保留最近30个10s窗口均值
        self._callbacks: List[Callable] = []
        self._last_window_ts = time.time()

    def register_window_callback(self, cb: Callable[..., Awaitable]):
        """注册窗口聚合结果回调"""
        self._callbacks.append(cb)

    def process(self, post: AnalyzedPost):
        """同步处理单条数据（Map算子）"""
        self._window_10s.add(post)
        self._window_60s.add(post)
        self._baseline_window.add(post)

        # KeyBy(topic) + 累计聚合
        for topic in post.topics:
            agg = self._topic_agg[topic]
            agg["count"] += 1
            agg["sentiment_sum"] += post.sentiment_score
            agg["heat_sum"] += post.heat_score
            # 话题关联（共现）
            for other in post.topics:
                if other != topic:
                    agg["related"].add(other)

        # 地域聚合
        if post.raw.region:
            ragg = self._region_agg[post.raw.region]
            ragg["count"] += 1
            ragg["heat_sum"] += post.heat_score
            if post.sentiment == Sentiment.negative:
                ragg["negative_count"] += 1

    async def tick(self):
        """
        定时触发窗口计算（模拟 Flink TriggerFunction）
        每10秒触发一次滚动窗口
        """
        now = time.time()
        if now - self._last_window_ts < 10:
            return
        self._last_window_ts = now

        result = self._compute_window_result()
        # 裁剪低热度话题，防止 _topic_agg 无限增长（保留 top200）
        if len(self._topic_agg) > 200:
            keep = sorted(self._topic_agg, key=lambda t: self._topic_agg[t]["heat_sum"], reverse=True)[:200]
            self._topic_agg = defaultdict(
                lambda: {"count": 0, "sentiment_sum": 0.0, "heat_sum": 0.0, "related": set()},
                {k: self._topic_agg[k] for k in keep},
            )
        for cb in self._callbacks:
            try:
                await cb(result)
            except Exception as e:
                logger.error(f"Window callback failed: {type(e).__name__}: {e}")

    def _compute_window_result(self) -> dict:
        items_10s = self._window_10s.items()
        items_60s = self._window_60s.items()
        baseline_items = self._baseline_window.items()

        # QPS（当前10s窗口 vs 基线）
        current_qps = len(items_10s) / 10.0
        baseline_qps = len(baseline_items) / 300.0 if baseline_items else current_qps

        # 情感均值（60s窗口）
        sentiment_avg_60s = (
            sum(p.sentiment_score for p in items_60s) / len(items_60s)
            if items_60s else 0.0
        )
        self._sentiment_ts.append(sentiment_avg_60s)

        # 情感骤降：当前值 vs 前5个窗口均值
        sentiment_drop = 0.0
        if len(self._sentiment_ts) >= 6:
            prev_avg = sum(list(self._sentiment_ts)[-6:-1]) / 5
            sentiment_drop = sentiment_avg_60s - prev_avg

        # TopN 话题（按热度）
        top_topics = sorted(
            [
                {
                    "id": topic,
                    "label": topic,
                    "heat": agg["heat_sum"],
                    "sentiment_avg": agg["sentiment_sum"] / max(agg["count"], 1),
                    "post_count": agg["count"],
                    "related": list(agg["related"])[:5],
                }
                for topic, agg in self._topic_agg.items()
            ],
            key=lambda x: x["heat"],
            reverse=True,
        )[:20]

        # 情感分布（10s窗口）
        sentiment_dist = {s.value: 0 for s in Sentiment}
        platform_dist: Dict[str, int] = defaultdict(int)
        for p in items_10s:
            sentiment_dist[p.sentiment.value] += 1
            platform_dist[p.raw.platform.value] += 1

        # 地域热度
        region_heat = [
            {
                "region": region,
                "count": agg["count"],
                "heat": agg["heat_sum"],
                "negative_rate": agg["negative_count"] / max(agg["count"], 1),
            }
            for region, agg in self._region_agg.items()
        ]

        return {
            "timestamp": datetime.now().isoformat(),
            "current_qps": round(current_qps, 2),
            "baseline_qps": round(baseline_qps, 2),
            "volume_ratio": round(current_qps / max(baseline_qps, 0.01), 2),
            "sentiment_avg_60s": round(sentiment_avg_60s, 3),
            "sentiment_drop": round(sentiment_drop, 3),
            "sentiment_distribution": sentiment_dist,
            "platform_distribution": dict(platform_dist),
            "top_topics": top_topics,
            "region_heat": region_heat,
            "posts_10s": len(items_10s),
            "posts_60s": len(items_60s),
        }

    def get_snapshot(self) -> dict:
        """获取当前状态快照（供 HTTP API 使用）"""
        return self._compute_window_result()
