"""
模拟 Kafka Producer：生成仿真社交媒体数据流
真实部署时替换为 kafka-python 的 KafkaProducer
"""
import asyncio
import random
import uuid
from datetime import datetime
from typing import AsyncGenerator

from models.schemas import RawPost, Platform

# 模拟内容库
TOPICS = [
    ("新能源汽车", ["续航", "充电桩", "比亚迪", "特斯拉", "补贴"]),
    ("人工智能", ["DeepSeek", "大模型", "ChatGPT", "算力", "监管"]),
    ("楼市调控", ["房价", "限购", "公积金", "降息", "库存"]),
    ("食品安全", ["添加剂", "抽检", "召回", "标准", "进口"]),
    ("体育赛事", ["世界杯", "奥运", "CBA", "转会", "冠军"]),
    ("娱乐八卦", ["明星", "出轨", "婚变", "综艺", "票房"]),
    ("医疗健康", ["医保", "药价", "挂号", "新药", "疫苗"]),
    ("教育内卷", ["高考", "双减", "留学", "培训", "就业"]),
]

POSITIVE_TEMPLATES = [
    "太棒了！{kw}真的很不错，强烈推荐大家关注！",
    "今天看到关于{kw}的好消息，感觉未来可期！",
    "支持{kw}，这是正确的方向，点赞！",
    "{kw}越来越好了，为相关从业者点赞！",
    "没想到{kw}能做到这一步，真心impressed！",
]

NEGATIVE_TEMPLATES = [
    "对{kw}真的很失望，这问题到底什么时候解决？",
    "{kw}这个情况太糟糕了，完全不可接受！",
    "受够了{kw}的问题，有关部门能不能管管？",
    "{kw}的现状让人心寒，普通人怎么办？",
    "关于{kw}，又在走老路，毫无新意还添乱！",
]

NEUTRAL_TEMPLATES = [
    "分享一下关于{kw}的最新动态，大家怎么看？",
    "{kw}相关政策今日发布，具体内容如下...",
    "有没有了解{kw}的朋友，求科普一下现状",
    "刚刚看到{kw}的数据报告，整理给大家",
    "关注{kw}很久了，说说我的观察",
]

REGIONS = [
    ("北京", "北京", 39.90, 116.40),
    ("上海", "上海", 31.23, 121.47),
    ("广州", "广东", 23.13, 113.26),
    ("深圳", "广东", 22.54, 114.05),
    ("成都", "四川", 30.57, 104.06),
    ("杭州", "浙江", 30.25, 120.15),
    ("武汉", "湖北", 30.59, 114.30),
    ("西安", "陕西", 34.27, 108.94),
    ("重庆", "重庆", 29.56, 106.55),
    ("南京", "江苏", 32.05, 118.77),
    ("天津", "天津", 39.12, 117.20),
    ("郑州", "河南", 34.75, 113.65),
    ("长沙", "湖南", 28.23, 112.93),
    ("沈阳", "辽宁", 41.80, 123.43),
    ("哈尔滨", "黑龙江", 45.75, 126.63),
]

AUTHORS = [f"用户_{random.randint(10000, 99999)}" for _ in range(200)]

async def generate_post_stream(rate: float = 5.0) -> AsyncGenerator[RawPost, None]:
    """
    生成模拟数据流，rate = 每秒生成条数
    真实场景替换为：async for msg in consumer: yield parse(msg)
    """
    interval = 1.0 / rate
    # 模拟突发事件（每60秒触发一次流量激增）
    burst_counter = 0

    while True:
        burst_counter += 1
        is_burst = burst_counter % 120 == 0  # 每120条触发一次激增

        topic_name, keywords = random.choice(TOPICS)
        kw = random.choice(keywords)
        sentiment_roll = random.random()

        # 激增时负面内容更多（模拟危机事件）
        if is_burst:
            sentiment_roll = random.uniform(0, 0.3)

        if sentiment_roll < 0.25:
            content = random.choice(NEGATIVE_TEMPLATES).format(kw=kw)
        elif sentiment_roll < 0.55:
            content = random.choice(NEUTRAL_TEMPLATES).format(kw=kw)
        else:
            content = random.choice(POSITIVE_TEMPLATES).format(kw=kw)

        city, province, lat, lng = random.choice(REGIONS)

        post = RawPost(
            id=str(uuid.uuid4())[:8],
            platform=random.choice(list(Platform)),
            content=content,
            author=random.choice(AUTHORS),
            region=city,
            likes=random.randint(0, 10000),
            reposts=random.randint(0, 5000),
            comments=random.randint(0, 2000),
            timestamp=datetime.now(),
            topic_keywords=[topic_name, kw],
        )

        yield post

        # 激增时短暂加速
        sleep_time = interval * 0.1 if is_burst else interval
        await asyncio.sleep(sleep_time)
