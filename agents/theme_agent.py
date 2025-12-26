"""
agents/theme_agent.py
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from app.orchestrator import AgentResponse, ThemeAgentProtocol


# =========================
# 型別 & Protocol 定義
# =========================

PromptTags = Dict[str, List[str]]


@dataclass
class ThemeCandidate:
    title: str
    short_concept: str
    prompt_tags: PromptTags
    nsfw_level: str = "sfw"
    meta: Dict[str, Any] = None


@runtime_checkable
class TrendFetcherProtocol(Protocol):
    def get_trending_tags(self, category: str = "anime", limit: int = 20) -> List[str]:
        ...


@runtime_checkable
class UserPreferenceStoreProtocol(Protocol):
    def get_theme_preferences(self) -> Dict[str, Any]:
        ...


@runtime_checkable
class PromptTemplateLibraryProtocol(Protocol):
    def get_base_template(self, template_name: str) -> PromptTags:
        ...


@runtime_checkable
class ModelRunnerProtocol(Protocol):
    def generate_themes(
        self,
        instruction: str,
        context: Dict[str, Any],
        count: int,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        ...


# =========================
# ThemeAgent 實作
# =========================

class ThemeAgent(ThemeAgentProtocol):

    def __init__(
        self,
        trend_fetcher: Optional[TrendFetcherProtocol] = None,
        user_prefs: Optional[UserPreferenceStoreProtocol] = None,
        prompt_templates: Optional[PromptTemplateLibraryProtocol] = None,
        model_runner: Optional[ModelRunnerProtocol] = None,
    ) -> None:
        self._trend_fetcher = trend_fetcher
        self._user_prefs = user_prefs
        self._prompt_templates = prompt_templates
        self._model_runner = model_runner

    # ========= Orchestrator 入口 ========= #

    def handle(self, payload: Dict[str, Any]) -> AgentResponse:
        try:
            # 1) 整理 payload
            count = int(payload.get("count", 3))
            if count <= 0: count = 1

            options = {
                "season": payload.get("season", "any"),
                "focus": payload.get("focus", "original_girl"),
                "platform": payload.get("platform", "x"),
                "count": count,
                "nsfw_level": payload.get("nsfw_level", "sfw"),
            }

            llm_config = payload.get("llm")

            # 2) 準備 trending + 偏好
            trending = self._trend_fetcher.get_trending_tags("anime", 30) if self._trend_fetcher else []
            preferences = self._user_prefs.get_theme_preferences() if self._user_prefs else {}

            # 3) 生成「主題」
            use_llm = self._model_runner is not None and llm_config is not None

            if use_llm:
                instruction = self._build_instruction()
                context = {
                    "options": options,
                    "trend_tags": trending,
                    "preferences": preferences,
                }
                
                # ModelRunner 回傳結構化資料 (這是為了讓程式能處理 Tag)
                raw_items = self._model_runner.generate_themes(
                    instruction=instruction,
                    context=context,
                    count=count,
                    llm_config=llm_config,
                )

                themes = []
                for item in raw_items:
                    # TIPO 處理完的 tags 會在 keywords 裡
                    # 這裡將其轉為 PromptTags 結構
                    keywords = item.get("keywords", [])
                    mood = item.get("mood", [])
                    
                    theme = ThemeCandidate(
                        title=item.get("title", "Untitled"),
                        short_concept=item.get("short_concept", ""),
                        prompt_tags=self._build_prompt_tags_from_keywords(
                            focus=options["focus"],
                            season=options["season"],
                            keywords=keywords,
                            mood=mood,
                        ),
                        nsfw_level=options["nsfw_level"],
                        meta={
                            "platform": options["platform"],
                            "season": options["season"],
                            "source": "llm",
                            "raw_keywords": keywords,
                        },
                    )
                    themes.append(theme)
            else:
                # Rule-based
                themes = self._generate_rule_based(options, trending, preferences)

            # 4) 【新增步驟】 將結果儲存為 .txt 到 output/
            saved_path = self._save_to_txt(themes, options)

            # 5) 回傳 API 響應
            # 我們依然回傳 data 給前端顯示，但多加一個 file_path 欄位告知儲存位置
            return AgentResponse(
                ok=True,
                data={
                    "message": f"Saved to {saved_path}",
                    "file_path": saved_path,
                    "themes": [self._theme_to_dict(t) for t in themes] # 前端仍可顯示卡片
                },
            )
        except Exception as e:
            return AgentResponse(ok=False, error=str(e))

    # ========= TXT 輸出邏輯 ========= #

    def _save_to_txt(self, themes: List[ThemeCandidate], options: Dict[str, Any]) -> str:
        """
        將生成的主題格式化為易讀的 TXT 並存檔。
        """
        # 1. 確保 output 資料夾存在
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)

        # 2. 產生檔名 (加入時間戳記)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"themes_{timestamp}.txt"
        filepath = os.path.join(output_dir, filename)

        # 3. 準備寫入內容
        lines = []
        lines.append(f"=== MCP Agent Generation Report ===")
        lines.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Request Options: {options}")
        lines.append("=" * 50 + "\n")

        for i, theme in enumerate(themes, 1):
            lines.append(f"Theme #{i}: {theme.title}")
            lines.append(f"Concept: {theme.short_concept}")
            lines.append("-" * 20)
            
            # 展平 Prompt Tags (變成直接可複製的格式)
            lines.append("[Calculated Tags]:")
            
            # 依照特定順序輸出比較好讀
            cat_order = ["clothing", "character", "setting", "mood", "action", "object", "artistic"]
            
            all_tags_flat = []
            
            for cat in cat_order:
                tags = theme.prompt_tags.get(cat, [])
                if tags:
                    tag_str = ", ".join(tags)
                    lines.append(f"  {cat.capitalize()}: {tag_str}")
                    all_tags_flat.extend(tags)
            
            # 處理其他沒在 order 裡的分類
            for cat, tags in theme.prompt_tags.items():
                if cat not in cat_order and tags:
                    lines.append(f"  {cat.capitalize()}: {', '.join(tags)}")
                    all_tags_flat.extend(tags)

            lines.append("-" * 20)
            lines.append("[Copy Paste String]:")
            lines.append(", ".join(all_tags_flat))
            
            lines.append("\n" + "=" * 50 + "\n")

        # 4. 寫入檔案
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        print(f"[ThemeAgent] Output saved to: {filepath}")
        return filepath

    # ========= 原有輔助方法 ========= #

    def _build_instruction(self) -> str:
        return (
            "You are a creative assistant for generating anime illustration themes. "
            "Based on the provided options (season, focus, etc.) and trending tags, "
            "generate distinct and interesting themes that fit the anime art style. "
            "Ensure variety in composition and mood."
        )

    def _build_prompt_tags_from_keywords(
        self,
        focus: str,
        season: str,
        keywords: List[str],
        mood: List[str],
    ) -> PromptTags:
        """
        將 LLM/TIPO 產生的 keywords 分類到 prompt_tags 結構。
        """
        base = self._get_base_prompt_template("default")
        tags = {k: list(v) for k, v in base.items()}

        # focus 預設放 clothing 或 character
        tags["clothing"].append(focus)

        # 簡單分類器 (可以根據需求擴充關鍵字)
        for kw in keywords:
            k = kw.lower()
            if any(x in k for x in ["bikini", "swimsuit", "uniform", "dress", "shirt", "skirt"]):
                tags["clothing"].append(kw)
            elif any(x in k for x in ["beach", "street", "room", "stage", "sky", "view", "indoor", "outdoor"]):
                tags["setting"].append(kw)
            elif any(x in k for x in ["smile", "blush", "sad", "angry", "look"]):
                tags["expression"].append(kw)
            elif any(x in k for x in ["sitting", "standing", "running", "lying"]):
                tags["action"].append(kw)
            elif any(x in k for x in ["masterpiece", "best quality", "absurdres"]):
                tags["artistic"].append(kw)
            else:
                # 預設丟到 object 或 general
                tags["object"].append(kw)

        tags["mood"].extend(mood)

        if season and season != "any":
            tags["setting"].append(season)

        # 去重
        for k in tags:
            tags[k] = list(dict.fromkeys(tags[k]))

        return tags

    def _generate_rule_based(self, options, trend_tags, prefs) -> List[ThemeCandidate]:
        # (保持原有的 Rule-based 邏輯不變，省略以節省篇幅)
        # 如果需要完整代碼請告訴我
        return [] 

    def _season_presets(self, season: str) -> tuple[str, List[str]]:
        season = (season or "any").lower()
        if season == "summer": return "beach", ["sunny", "bright"]
        if season == "winter": return "snowy_city", ["cozy", "quiet"]
        return "room", ["daily"]

    def _get_base_prompt_template(self, template_name: str) -> PromptTags:
        return {
            "clothing": [], "mood": [], "setting": [], 
            "expression": [], "action": [], "artistic": [], "object": []
        }

    def _theme_to_dict(self, theme: ThemeCandidate) -> Dict[str, Any]:
        d = asdict(theme)
        if d["meta"] is None: d["meta"] = {}
        return d