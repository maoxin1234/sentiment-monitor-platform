"""
异常舆情检测器
检测规则：
  1. 负面率骤升（10s窗口负面率 > 阈值）
  2. 流量激增（当前QPS > 基线 * 倍数）
  3. 情感骤降（60s均值骤降超过阈值）
  4. 热度话题负面化（单话题负面率高）
"""
import uuid
from datetime import datetime
from typing import List, Dict
from collections import defaultdict
import time

from config import config
from models.schemas import AlertEvent, AlertLevel


class AnomalyDetector:
    def __init__(self):
        self._alert_cooldown: Dict[str, float] = {}  # key -> last_alert_ts
        self._active_alerts: List[AlertEvent] = []
        self._alert_history: List[AlertEvent] = []
        self._cfg = config.alert

    def _in_cooldown(self, key: str) -> bool:
        last = self._alert_cooldown.get(key, 0)
        return time.time() - last < self._cfg.cooldown_seconds

    def _fire(self, alert: AlertEvent):
        key = f"{alert.trigger_metric}:{alert.topic or alert.platform or 'global'}"
        if self._in_cooldown(key):
            return None
        self._alert_cooldown[key] = time.time()
        self._active_alerts.append(alert)
        self._alert_history.append(alert)
        # 只保留最近100条历史
        if len(self._alert_history) > 100:
            self._alert_history.pop(0)
        return alert

    def detect(self, window_result: dict) -> List[AlertEvent]:
        """输入 FlinkStreamProcessor 的窗口结果，返回新触发的告警列表"""
        alerts = []

        # 1. 流量激增检测
        volume_ratio = window_result.get("volume_ratio", 1.0)
        if volume_ratio > self._cfg.volume_spike_threshold:
            level = AlertLevel.critical if volume_ratio > 5 else AlertLevel.warning
            alert = self._fire(AlertEvent(
                id=str(uuid.uuid4())[:8],
                level=level,
                title="⚡ 流量激增告警",
                description=f"当前QPS是基线的 {volume_ratio:.1f} 倍，疑似热点事件爆发",
                trigger_metric="volume_ratio",
                current_value=volume_ratio,
                threshold=self._cfg.volume_spike_threshold,
                timestamp=datetime.now(),
            ))
            if alert:
                alerts.append(alert)

        # 2. 情感骤降检测
        sentiment_drop = window_result.get("sentiment_drop", 0.0)
        if sentiment_drop < self._cfg.sentiment_drop_threshold:
            alert = self._fire(AlertEvent(
                id=str(uuid.uuid4())[:8],
                level=AlertLevel.warning,
                title="📉 舆情情感骤降",
                description=f"情感均值骤降 {abs(sentiment_drop):.2f}，舆论风向快速转负",
                trigger_metric="sentiment_drop",
                current_value=sentiment_drop,
                threshold=self._cfg.sentiment_drop_threshold,
                timestamp=datetime.now(),
            ))
            if alert:
                alerts.append(alert)

        # 3. 话题负面率检测
        for topic_data in window_result.get("top_topics", []):
            sentiment_avg = topic_data.get("sentiment_avg", 0.0)
            post_count = topic_data.get("post_count", 0)
            # 只有一定热度的话题才触发
            if post_count >= 5 and sentiment_avg < -0.4:
                negative_rate = (1 - sentiment_avg) / 2  # 映射到0~1
                alert = self._fire(AlertEvent(
                    id=str(uuid.uuid4())[:8],
                    level=AlertLevel.warning,
                    title=f"🔴 话题负面告警：{topic_data['label']}",
                    description=f"话题「{topic_data['label']}」情感均值 {sentiment_avg:.2f}，负面情绪集中",
                    trigger_metric="topic_sentiment",
                    current_value=sentiment_avg,
                    threshold=-0.4,
                    topic=topic_data["label"],
                    timestamp=datetime.now(),
                ))
                if alert:
                    alerts.append(alert)

        # 4. 全局负面率检测
        dist = window_result.get("sentiment_distribution", {})
        total = sum(dist.values())
        if total > 0:
            neg_rate = dist.get("负面", 0) / total
            if neg_rate > self._cfg.negative_rate_threshold:
                alert = self._fire(AlertEvent(
                    id=str(uuid.uuid4())[:8],
                    level=AlertLevel.critical if neg_rate > 0.75 else AlertLevel.warning,
                    title="🚨 全局负面率超阈值",
                    description=f"当前负面帖子占比 {neg_rate:.0%}，超过安全阈值 {self._cfg.negative_rate_threshold:.0%}",
                    trigger_metric="negative_rate",
                    current_value=neg_rate,
                    threshold=self._cfg.negative_rate_threshold,
                    timestamp=datetime.now(),
                ))
                if alert:
                    alerts.append(alert)

        # 清理已确认的告警
        self._active_alerts = [a for a in self._active_alerts if not a.acknowledged]

        return alerts

    def acknowledge(self, alert_id: str) -> bool:
        for alert in self._active_alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def get_active_alerts(self) -> List[AlertEvent]:
        return [a for a in self._active_alerts if not a.acknowledged]

    def get_history(self) -> List[AlertEvent]:
        return list(reversed(self._alert_history))


detector = AnomalyDetector()
