"""
多模型协同路由器
策略：
  local_first  - 优先本地，失败/超时自动降级到云端
  cloud_first  - 优先云端，成本敏感时降级到本地
  load_balance - 按负载动态分配
  cost_aware   - 短文本用本地，长文本/复杂分析用云端
"""
import asyncio
import time
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)
from config import config


class ModelClient:
    def __init__(self, base_url: str, model: str, api_key: str, max_concurrent: int):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._success = 0
        self._failure = 0
        self._total_ms = 0

    @property
    def avg_latency_ms(self) -> float:
        total = self._success + self._failure
        return self._total_ms / max(total, 1)

    @property
    def success_rate(self) -> float:
        total = self._success + self._failure
        return self._success / max(total, 1)

    async def chat(self, system: str, user: str, timeout: float = 8.0) -> Optional[str]:
        async with self._semaphore:
            t0 = time.time()
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={
                            "model": self.model,
                            "messages": [
                                {"role": "system", "content": system},
                                {"role": "user", "content": user},
                            ],
                            "max_tokens": 256,
                            "temperature": 0.3,
                        },
                    )
                    resp.raise_for_status()
                    result = resp.json()["choices"][0]["message"]["content"]
                    self._success += 1
                    self._total_ms += int((time.time() - t0) * 1000)
                    return result
            except Exception as e:
                self._failure += 1
                self._total_ms += int((time.time() - t0) * 1000)
                logger.debug(f"Model {self.model} request failed: {type(e).__name__}")
                return None

    def stats(self) -> dict:
        return {
            "model": self.model,
            "success": self._success,
            "failure": self._failure,
            "avg_latency_ms": round(self.avg_latency_ms),
            "success_rate": round(self.success_rate, 3),
        }


class LLMRouter:
    def __init__(self):
        cfg = config.llm
        self.local = ModelClient(
            cfg.local_base_url, cfg.local_model, cfg.local_api_key,
            cfg.max_concurrent_local,
        )
        self.cloud = ModelClient(
            cfg.cloud_base_url, cfg.cloud_model, cfg.cloud_api_key,
            cfg.max_concurrent_cloud,
        )
        self.strategy = cfg.routing_strategy
        self.complexity_threshold = cfg.complexity_threshold
        self._local_count = 0
        self._cloud_count = 0

    def _estimate_complexity(self, text: str) -> float:
        """简单复杂度估算：长度 + 特殊字符密度"""
        length_score = min(len(text) / 500, 1.0)
        special_ratio = sum(1 for c in text if not c.isalnum()) / max(len(text), 1)
        return length_score * 0.7 + special_ratio * 0.3

    async def chat(self, system: str, user: str) -> tuple[Optional[str], str]:
        """
        返回 (content, used_model)
        """
        complexity = self._estimate_complexity(user)

        if self.strategy == "local_first":
            result = await self.local.chat(system, user, timeout=6.0)
            if result:
                self._local_count += 1
                return result, "local"
            result = await self.cloud.chat(system, user, timeout=15.0)
            if result:
                self._cloud_count += 1
            return result, "cloud"

        elif self.strategy == "cloud_first":
            result = await self.cloud.chat(system, user, timeout=15.0)
            if result:
                self._cloud_count += 1
                return result, "cloud"
            result = await self.local.chat(system, user, timeout=6.0)
            if result:
                self._local_count += 1
            return result, "local"

        elif self.strategy == "cost_aware":
            # 复杂内容走云端，简单内容走本地
            if complexity > self.complexity_threshold:
                result = await self.cloud.chat(system, user, timeout=15.0)
                if result:
                    self._cloud_count += 1
                    return result, "cloud"
            result = await self.local.chat(system, user, timeout=6.0)
            if result:
                self._local_count += 1
                return result, "local"
            result = await self.cloud.chat(system, user, timeout=15.0)
            self._cloud_count += 1
            return result, "cloud"

        else:  # load_balance
            # 按成功率加权选择
            local_weight = self.local.success_rate + 0.1
            cloud_weight = self.cloud.success_rate
            import random
            if random.random() < local_weight / (local_weight + cloud_weight):
                result = await self.local.chat(system, user, timeout=6.0)
                if result:
                    self._local_count += 1
                    return result, "local"
            result = await self.cloud.chat(system, user, timeout=15.0)
            self._cloud_count += 1
            return result, "cloud"

    def stats(self) -> dict:
        total = self._local_count + self._cloud_count
        return {
            "strategy": self.strategy,
            "local_count": self._local_count,
            "cloud_count": self._cloud_count,
            "local_ratio": round(self._local_count / max(total, 1), 3),
            "local": self.local.stats(),
            "cloud": self.cloud.stats(),
        }


llm_router = LLMRouter()
