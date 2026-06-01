"""
告警推送渠道
支持：Webhook（企业微信/飞书/钉钉） | 邮件 | WebSocket实时推送
"""
import asyncio
import httpx
from typing import List, Callable, Awaitable

from config import config
from models.schemas import AlertEvent, AlertLevel


def _level_color(level: AlertLevel) -> str:
    return {"info": "green", "warning": "yellow", "critical": "red"}.get(level, "grey")


def _build_feishu_card(alert: AlertEvent) -> dict:
    """飞书消息卡片格式"""
    color = _level_color(alert.level)
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": alert.title},
                "template": color,
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": alert.description}},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**触发指标**: {alert.trigger_metric}\n"
                            f"**当前值**: {alert.current_value:.3f}  "
                            f"**阈值**: {alert.threshold:.3f}\n"
                            f"**时间**: {alert.timestamp.strftime('%H:%M:%S')}"
                        ),
                    },
                },
            ],
        },
    }


def _build_dingtalk_markdown(alert: AlertEvent) -> dict:
    """钉钉 Markdown 消息格式"""
    return {
        "msgtype": "markdown",
        "markdown": {
            "title": alert.title,
            "text": (
                f"## {alert.title}\n\n"
                f"{alert.description}\n\n"
                f"- **指标**: {alert.trigger_metric}\n"
                f"- **当前值**: {alert.current_value:.3f}\n"
                f"- **阈值**: {alert.threshold:.3f}\n"
                f"- **时间**: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            ),
        },
        "at": {"isAtAll": alert.level == AlertLevel.critical},
    }


class AlertNotifier:
    def __init__(self):
        self._ws_callbacks: List[Callable[[dict], Awaitable]] = []

    def register_ws_callback(self, cb: Callable[[dict], Awaitable]):
        """注册 WebSocket 推送回调（由 main.py 设置）"""
        self._ws_callbacks.append(cb)

    async def notify(self, alerts: List[AlertEvent]):
        if not alerts:
            return
        tasks = []
        for alert in alerts:
            payload = alert.model_dump(mode="json")
            # WebSocket 实时推送（必须）
            tasks.append(self._push_ws(payload))
            # Webhook 推送（可选）
            if config.alert.webhook_url:
                tasks.append(self._push_webhook(alert))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _push_ws(self, payload: dict):
        for cb in self._ws_callbacks:
            try:
                await cb({"type": "alert", "data": payload})
            except Exception:
                pass

    async def _push_webhook(self, alert: AlertEvent):
        url = config.alert.webhook_url
        if not url:
            return
        # 自动识别飞书/钉钉/企业微信/通用
        if "feishu" in url or "larksuite" in url:
            body = _build_feishu_card(alert)
        elif "dingtalk" in url:
            body = _build_dingtalk_markdown(alert)
        else:
            body = alert.model_dump(mode="json")
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(url, json=body)
        except Exception:
            pass


notifier = AlertNotifier()
