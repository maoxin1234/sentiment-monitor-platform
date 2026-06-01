"""
社交媒体舆情实时监控平台 - 后端主入口
架构：Mock/Kafka Source -> Flink Window -> LLM Analysis -> WebSocket -> Frontend
"""
import asyncio
import json
import time
import logging
import os
from contextlib import asynccontextmanager
from typing import Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

from config import config
from stream.mock_producer import generate_post_stream
from stream.flink_processor import FlinkStreamProcessor
from analysis.sentiment_analyzer import analyze_post
from alert.detector import detector
from alert.notifier import notifier
from analysis.llm_router import llm_router
from models.schemas import AlertEvent

# ── 全局状态 ──────────────────────────────────────────────────────────────────
flink = FlinkStreamProcessor()
ws_clients: Set[WebSocket] = set()
recent_posts: list = []          # 最近50条已分析帖子
total_today: int = 0
start_time: float = time.time()


async def broadcast(message: dict):
    """广播消息到所有 WebSocket 连接"""
    if not ws_clients:
        return
    data = json.dumps(message, ensure_ascii=False, default=str)
    dead = set()
    for ws in ws_clients:
        try:
            await ws.send_text(data)
        except Exception:
            dead.add(ws)
    ws_clients.difference_update(dead)  # in-place，避免 Python 将 ws_clients 识别为局部变量


async def on_window_result(result: dict):
    """Flink 窗口结果回调 -> 检测告警 -> 广播"""
    # 告警检测
    alerts = detector.detect(result)
    if alerts:
        await notifier.notify(alerts)

    await broadcast({"type": "window", "data": result})


async def stream_pipeline():
    """主流水线：数据源 -> Flink处理 -> LLM分析 -> 广播"""
    global total_today
    use_llm = bool(config.llm.cloud_api_key)
    logger.info(f"Pipeline started: use_llm={use_llm}, rate={config.mock_rate}")

    try:
        async for raw_post in generate_post_stream(rate=config.mock_rate):
            try:
                analyzed = await analyze_post(raw_post, use_llm=use_llm)
                flink.process(analyzed)
                total_today += 1

                post_dict = {
                    "id": analyzed.raw.id,
                    "platform": analyzed.raw.platform.value,
                    "content": analyzed.raw.content[:60],
                    "author": analyzed.raw.author,
                    "region": analyzed.raw.region,
                    "sentiment": analyzed.sentiment.value,
                    "sentiment_score": analyzed.sentiment_score,
                    "emotion": analyzed.emotion,
                    "topics": analyzed.topics,
                    "summary": analyzed.summary,
                    "heat": analyzed.heat_score,
                    "processed_by": analyzed.processed_by,
                    "processing_ms": analyzed.processing_ms,
                    "timestamp": analyzed.raw.timestamp.isoformat(),
                }
                recent_posts.insert(0, post_dict)
                if len(recent_posts) > 50:
                    recent_posts.pop()

                if total_today % 20 == 0:
                    logger.info(f"Pipeline progress: {total_today} posts processed")

                await broadcast({"type": "post", "data": recent_posts[0]})
                await flink.tick()
            except Exception as e:
                logger.error(f"Post processing error (id={getattr(raw_post, 'id', '?')}): {type(e).__name__}: {e}", exc_info=True)
    except Exception as e:
        logger.critical(f"Pipeline fatal error: {e}", exc_info=True)


# ── 生命周期 ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    flink.register_window_callback(on_window_result)
    notifier.register_ws_callback(broadcast)
    task = asyncio.create_task(stream_pipeline())
    yield
    task.cancel()


# ── FastAPI 应用 ───────────────────────────────────────────────────────────────
app = FastAPI(title="舆情监控平台", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载前端静态文件
import os, pathlib
frontend_dir = pathlib.Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


# ── HTTP API ──────────────────────────────────────────────────────────────────
@app.get("/")
async def index():
    index_file = frontend_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"status": "ok", "message": "舆情监控平台运行中"}


@app.get("/api/stats")
async def get_stats():
    snapshot = flink.get_snapshot()
    elapsed = max(time.time() - start_time, 1)
    return {
        **snapshot,
        "total_today": total_today,
        "posts_per_second": round(total_today / elapsed, 2),
        "active_alerts": len(detector.get_active_alerts()),
        "llm_stats": llm_router.stats(),
    }


@app.get("/api/posts")
async def get_recent_posts(limit: int = 20):
    return recent_posts[:limit]


@app.get("/api/alerts")
async def get_alerts():
    return {
        "active": [a.model_dump(mode="json") for a in detector.get_active_alerts()],
        "history": [a.model_dump(mode="json") for a in detector.get_history()[:20]],
    }


@app.post("/api/alerts/{alert_id}/ack")
async def acknowledge_alert(alert_id: str):
    ok = detector.acknowledge(alert_id)
    return {"success": ok}


@app.get("/api/llm/stats")
async def get_llm_stats():
    return llm_router.stats()


# ── WebSocket ─────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    try:
        # 发送初始快照
        await ws.send_text(json.dumps({
            "type": "init",
            "data": flink.get_snapshot(),
        }, ensure_ascii=False, default=str))

        while True:
            # 心跳保活
            await asyncio.sleep(config.ws_heartbeat)
            await ws.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        ws_clients.discard(ws)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False, log_level="info")
