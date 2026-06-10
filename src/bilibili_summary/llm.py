from __future__ import annotations

import json
import httpx
from pydantic import BaseModel, Field, ValidationError

from .models import SummaryResult, VideoMetadata


CLASSIFY_SYSTEM = "你是一个严格的视频分类器，只输出 JSON。"

SUMMARY_SYSTEM = """# Role
你是一位拥有经验的资深速记整理与文稿润色专家，负责将视频 STT 稿件转化为可以发表的中文深度长文。

# Input Pre-check
如果输入是歌曲 MV、纯歌词、环境噪音、无意义音频、缺乏实质叙事核心的超短片段，严禁生成深度长文，ai_html_content 返回“暂无总结”。

# Task
检测 STT 主要语言；非中文翻译为流畅中文，保留关键技术术语英文原词。修正 STT 错字，去除口癖，合并碎片口语，但不得删除事实、数据、案例或个人轶事。按照演讲自然顺序分段，禁止要点式归纳。

# HTML
使用 blockquote、h2、p、strong、hr。除非原演讲确实罗列条款，否则不要使用 ul/li。

只输出 JSON：{"ai_title":"...","ai_html_content":"...","tags":["AI-Summary","..."]}。
"""


class Classification(BaseModel):
    is_food: bool = Field(description="是否属于美食/烹饪视频")
    reason: str


class SummaryPayload(BaseModel):
    ai_title: str
    ai_html_content: str
    tags: list[str]


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def classify_food(self, metadata: VideoMetadata) -> Classification:
        user = (
            "请判断这个 B站视频是否属于【美食/烹饪】视频。\n\n"
            "## 美食/烹饪的定义（is_food=true）\n"
            "只有以下情况才判定为美食/烹饪视频：\n"
            "- 烹饪教程/食谱分享（炒菜、烘焙、料理制作过程）\n"
            "- 美食评测/餐厅探店（成品美食品尝、餐厅菜品展示）\n"
            "- 烹饪技巧/厨艺教学（刀工、调味、烹饪方法讲解）\n"
            "- 美食纪录片（聚焦烹饪过程或成品美食，而非食材种植）\n\n"
            "## 排除范围（is_food=false）\n"
            "以下情况**不是**美食/烹饪视频，即使与食物相关也不算：\n"
            "- 水果种植/农业科普（果树栽培、农产品种植技术）\n"
            "- 生物/自然科普（动植物生长、生态环境、食材来源）\n"
            "- 农产品介绍/产地溯源（侧重产地而非烹饪）\n"
            "- 食品工业/加工工艺（工厂生产线、食品制造技术）\n"
            "- 饮品/咖啡/茶艺（除非涉及食物搭配）\n\n"
            "## 判断原则\n"
            "- 核心是【烹饪过程】或【成品美食展示】才算\n"
            "- 只涉及食材来源/种植/生物 = 不算\n"
            "- 标题含\"种植\"\"农业\"\"水果\"\"采摘\"等关键词 = 不算\n\n"
            f"标题：{metadata.title}\n"
            f"分区：{metadata.category_name or ''}\n"
            f"UP主：{metadata.owner_name or ''}\n"
            f"简介：{metadata.description or ''}\n"
            f"动态：{metadata.dynamic or ''}\n"
            "只输出 JSON：{\"is_food\": true/false, \"reason\": \"...\"}"
        )
        data = self._chat(CLASSIFY_SYSTEM, user)
        return Classification.model_validate(_json_from_text(data))

    def summarize(self, metadata: VideoMetadata, stt_text: str) -> SummaryResult:
        user = f"视频原始标题为 {metadata.title}\n\nSTT 结果为 {stt_text}"
        data = self._chat(SUMMARY_SYSTEM, user)
        try:
            payload = SummaryPayload.model_validate(_json_from_text(data))
        except ValidationError as exc:
            raise RuntimeError(f"Invalid summary JSON: {exc}") from exc
        return SummaryResult(payload.ai_title, payload.ai_html_content, payload.tags)

    def _chat(self, system: str, user: str) -> str:
        if not self.base_url or not self.api_key:
            raise RuntimeError("LLM_BASE_URL and LLM_API_KEY are required for LLM operations")
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
            },
            timeout=600,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def _json_from_text(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise RuntimeError(f"LLM response did not contain JSON: {text[:200]}")
    return json.loads(stripped[start:end + 1])
