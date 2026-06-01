"""
情感分析引擎
轻量级规则分析（无需LLM，用于高吞吐场景）+ LLM深度分析
"""
import time
import re
from typing import Tuple

from models.schemas import RawPost, AnalyzedPost, Sentiment
from analysis.llm_router import llm_router

# 情感词典（简化版，生产环境替换为 SnowNLP / BERT / 知网情感词典）
POSITIVE_WORDS = {
    "棒", "好", "赞", "支持", "喜欢", "优秀", "强烈推荐", "点赞", "期待",
    "可期", "不错", "出色", "厉害", "完美", "感谢", "进步", "改善", "成功",
    "突破", "impressive", "amazing", "great",
}
NEGATIVE_WORDS = {
    "糟糕", "失望", "愤怒", "不满", "抗议", "投诉", "问题", "不可接受",
    "心寒", "受够", "可恶", "垃圾", "差劲", "骗", "坑", "崩溃", "倒闭",
    "造假", "违规", "危险", "恐慌", "担心", "害怕", "恶心",
}
EMOTION_MAP = {
    ("愤怒", "愤", "怒", "可恶", "受够", "不满"): "愤怒",
    ("喜悦", "开心", "高兴", "棒", "赞", "点赞"): "喜悦",
    ("悲伤", "难过", "心寒", "失望", "遗憾"): "悲伤",
    ("恐惧", "担心", "害怕", "恐慌", "危险"): "恐惧",
    ("惊讶", "没想到", "震惊", "意外", "竟然"): "惊讶",
}

SYSTEM_PROMPT = """你是一个专业的中文社交媒体舆情分析师。
分析用户提供的社交媒体文本，返回如下JSON格式（不要有其他内容）：
{
  "sentiment": "正面|中性|负面",
  "score": <-1.0到1.0的浮点数>,
  "emotion": "愤怒|喜悦|悲伤|恐惧|惊讶|中性",
  "topics": ["话题1", "话题2"],
  "summary": "一句话摘要（15字内）"
}"""


def _rule_based_analyze(text: str) -> Tuple[Sentiment, float, str]:
    """基于词典的快速情感分析，延迟<1ms"""
    pos_count = sum(1 for w in POSITIVE_WORDS if w in text)
    neg_count = sum(1 for w in NEGATIVE_WORDS if w in text)

    score = (pos_count - neg_count) / max(pos_count + neg_count, 1)
    score = max(-1.0, min(1.0, score))

    if score > 0.1:
        sentiment = Sentiment.positive
    elif score < -0.1:
        sentiment = Sentiment.negative
    else:
        sentiment = Sentiment.neutral

    emotion = "中性"
    for keywords, emo in EMOTION_MAP.items():
        if any(k in text for k in keywords):
            emotion = emo
            break

    return sentiment, score, emotion


async def analyze_post(raw: RawPost, use_llm: bool = True) -> AnalyzedPost:
    """
    分析单条帖子
    use_llm=True 时调用 LLM 深度分析，否则仅规则分析
    """
    t0 = time.time()

    # 快速规则分析（兜底）
    sentiment, score, emotion = _rule_based_analyze(raw.content)
    topics = list(raw.topic_keywords)
    summary = raw.content[:30] + "..."
    processed_by = "rule"

    if use_llm:
        try:
            content, model_type = await llm_router.chat(
                system=SYSTEM_PROMPT,
                user=f"文本：{raw.content}\n平台：{raw.platform.value}\n关键词：{','.join(raw.topic_keywords)}",
            )
            if content:
                import json
                # 提取JSON（LLM可能返回多余文字）
                match = re.search(r'\{.*?\}', content, re.DOTALL)
                if match:
                    data = json.loads(match.group())
                    sentiment_map = {"正面": Sentiment.positive, "负面": Sentiment.negative, "中性": Sentiment.neutral}
                    sentiment = sentiment_map.get(data.get("sentiment", "中性"), Sentiment.neutral)
                    score = float(data.get("score", score))
                    emotion = data.get("emotion", emotion)
                    topics = data.get("topics", topics) or topics
                    summary = data.get("summary", summary)
                    processed_by = model_type
        except Exception:
            pass  # 降级到规则结果

    heat = raw.likes * 1 + raw.reposts * 3 + raw.comments * 2
    processing_ms = int((time.time() - t0) * 1000)

    return AnalyzedPost(
        raw=raw,
        sentiment=sentiment,
        sentiment_score=score,
        emotion=emotion,
        topics=topics,
        summary=summary,
        heat_score=float(heat),
        processed_by=processed_by,
        processing_ms=processing_ms,
    )
