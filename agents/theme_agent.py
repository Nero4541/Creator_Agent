from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from app.orchestrator import AgentResponse, ThemeAgentProtocol


# =========================
# 型別 & Protocol 定義
# =========================

PromptTags = Dict[str, List[str]]  # 例：{"clothing": [...], "mood": [...], ...}


@dataclass
class ThemeCandidate:
    """
    ThemeAgent 產生的一個主題候選。

    - title: 主題標題（用在貼文、檔名）
    - short_concept: 一句話的概念描述
    - prompt_tags: 已分類好的 Danbooru / tag 結構
    - nsfw_level: "sfw" / "mild" / "nsfw" 等級
    - meta: 其他你想存的資料（季節、平台、趨勢 tag 等）
    """
    title: str
    short_concept: str
    prompt_tags: PromptTags
    nsfw_level: str = "sfw"
    meta: Dict[str, Any] = None


# ---- Skills 層的介面（之後在 skills/ 裡實作） ---- #

@runtime_checkable
class TrendFetcherProtocol(Protocol):
    def get_trending_tags(
        self,
        category: str = "anime",
        limit: int = 20,
    ) -> List[str]:
        """
        回傳近期熱門 tag（例如從 X / Pixiv / 你手動整理的列表）
        """
        ...


@runtime_checkable
class UserPreferenceStoreProtocol(Protocol):
    def get_theme_preferences(self) -> Dict[str, Any]:
        """
        回傳與主題生成相關的偏好設定，例如：
        {
          "default_style": "anime",
          "allowed_nsfw_level": "sfw",
          "favorite_motifs": ["frilled_bikini", "school_uniform"],
          "ng_tags": ["gore", "violence"]
        }
        """
        ...


@runtime_checkable
class PromptTemplateLibraryProtocol(Protocol):
    def get_base_template(self, template_name: str) -> PromptTags:
        """
        回傳一個 base prompt 結構（還沒有塞主題），例如：

        {
          "clothing": [],
          "mood": [],
          "setting": [],
          "expression": [],
          "action": [],
          "artistic": []
        }
        """
        ...


@runtime_checkable
class ModelRunnerProtocol(Protocol):
    def generate_themes(
        self,
        instruction: str,
        context: Dict[str, Any],
        count: int,
    ) -> List[Dict[str, Any]]:
        """
        如果你將來想用 LLM 來幫忙想主題，就實作這個。

        回傳格式範例（自由但建議一致）：
        [
          {
            "title": "...",
            "short_concept": "...",
            "keywords": ["sunset", "beach", "frilled_bikini"],
            "mood": ["shy", "romantic"],
          },
          ...
        ]
        """
        ...


# =========================
# ThemeAgent 實作
# =========================

class ThemeAgent(ThemeAgentProtocol):
    """
    專門處理「主題 & Prompt」相關任務的 Agent。

    - 支援目前的需求：給我幾個主題 + Danbooru 風 tag 結構
    - 未來可以：
        - 加入 LLM（透過 ModelRunnerProtocol）
        - 讀取真實的 trending 資料
        - 根據你作品的歷史來調整主題
    """

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
        """
        Orchestrator 入口：處理主題生成請求。
        """
        try:
            # 1) 整理 payload
            count = int(payload.get("count", 3))
            if count <= 0:
                count = 1

            options = {
                "season": payload.get("season", "any"),
                "focus": payload.get("focus", "original_girl"),
                "platform": payload.get("platform", "x"),
                "count": count,
                "nsfw_level": payload.get("nsfw_level", "sfw"),
            }

            llm_config = payload.get("llm")  # WebUI 傳進來的 LLM 設定

            # 2) 準備 trending + 偏好
            trending = (
                self._trend_fetcher.get_trending_tags("anime", 30)
                if self._trend_fetcher
                else []
            )
            preferences = (
                self._user_prefs.get_theme_preferences()
                if self._user_prefs
                else {}
            )

            # 3) 生成「主題」本體（使用 LLM or rule-based）
            use_llm = self._model_runner is not None and llm_config is not None

            if use_llm:
                # LLM 版
                instruction = self._build_instruction()
                context = {
                    "options": options,
                    "trend_tags": trending,
                    "preferences": preferences,
                }

                raw_items = self._model_runner.generate_themes(
                    instruction=instruction,
                    context=context,
                    count=count,
                    llm_config=llm_config,
                )

                # 轉成 ThemeCandidate
                themes = []
                for item in raw_items:
                    theme = ThemeCandidate(
                        title=item.get("title", "Untitled"),
                        short_concept=item.get("short_concept", ""),
                        prompt_tags=self._build_prompt_tags_from_keywords(
                            focus=options["focus"],
                            season=options["season"],
                            keywords=item.get("keywords", []),
                            mood=item.get("mood", []),
                        ),
                        nsfw_level=options["nsfw_level"],
                        meta={
                            "platform": options["platform"],
                            "season": options["season"],
                            "source": "llm",
                            "raw_keywords": item.get("keywords", []),
                        },
                    )
                    themes.append(theme)
            else:
                # Rule-based 版
                themes = self._generate_rule_based(
                    options=options,
                    trend_tags=trending,
                    prefs=preferences,
                )

            # 4) 回傳格式
            return AgentResponse(
                ok=True,
                data=[self._theme_to_dict(t) for t in themes],
            )
        except Exception as e:
            return AgentResponse(ok=False, error=str(e))

    def _build_instruction(self) -> str:
        """
        回傳給 LLM 的核心指令 (Instruction)。
        """
        return (
            "You are a creative assistant for generating anime illustration themes. "
            "Based on the provided options (season, focus, etc.) and trending tags, "
            "generate distinct and interesting themes that fit the anime art style. "
            "Ensure variety in composition and mood."
        )
    # ========= Payload 處理 ========= #

    def _normalize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        簡單整理 payload，補上預設值，避免 KeyError。
        """
        count = int(payload.get("count", 3))
        if count <= 0:
            count = 1

        return {
            "count": count,
            "season": payload.get("season", "any"),
            "focus": payload.get("focus", "original_girl"),
            "platform": payload.get("platform", "X"),
            "nsfw_level": payload.get("nsfw_level", "sfw"),
        }

    # ========= Context 準備 ========= #

    def _fetch_trending_tags(self) -> List[str]:
        """
        從 TrendFetcher 拿熱門 tag，如果沒有就回傳幾個預設的。
        """
        if self._trend_fetcher is None:
            return []
        return self._trend_fetcher.get_trending_tags(...)


    def _load_preferences(self) -> Dict[str, Any]:
        """
        從 UserPreferenceStore 讀使用者偏好。
        """
        if self._user_prefs is None:
           return {}
        return self._user_prefs.get_theme_preferences()

    # ========= 主題生成：LLM 版 ========= #

    def _generate_with_model(
        self,
        options: Dict[str, Any],
        trend_tags: List[str],
        prefs: Dict[str, Any],
    ) -> List[ThemeCandidate]:
        """
        如果你有接 LLM，可以在這裡寫 prompt，把 LLM 回傳的結果轉成 ThemeCandidate。
        先給一個示意骨架。
        """
        instruction = (
            "你是一個幫助創作二次元插畫主題的助手，"
            "請根據給定的季節、焦點元素、趨勢 tag 和使用者偏好，"
            "生成適合在 SNS 上發布的插畫主題。"
        )

        context = {
            "options": options,
            "trend_tags": trend_tags,
            "preferences": prefs,
        }

        raw_items = self._model_runner.generate_themes(
            instruction=instruction,
            context=context,
            count=options["count"],
        )

        themes: List[ThemeCandidate] = []
        for item in raw_items:
            title = item.get("title", "Untitled Theme")
            short_concept = item.get("short_concept", "")
            keywords = item.get("keywords", [])
            mood = item.get("mood", [])

            prompt_tags = self._build_prompt_tags_from_keywords(
                focus=options["focus"],
                season=options["season"],
                keywords=keywords,
                mood=mood,
            )

            theme = ThemeCandidate(
                title=title,
                short_concept=short_concept,
                prompt_tags=prompt_tags,
                nsfw_level=options["nsfw_level"],
                meta={
                    "season": options["season"],
                    "platform": options["platform"],
                    "source": "model",
                    "raw_keywords": keywords,
                },
            )
            themes.append(theme)

        return themes

    # ========= 主題生成：Rule-based 版（預設用這個） ========= #

    def _generate_rule_based(
        self,
        options: Dict[str, Any],
        trend_tags: List[str],
        prefs: Dict[str, Any],
    ) -> List[ThemeCandidate]:
        """
        不依賴 LLM 的主題生成方式：
        - 根據季節組合場景（海邊、校園、祭典…）
        - 根據 focus + favorite_motifs 加進 clothing / motif
        - 從 trending 裡抽幾個補強
        """
        count = options["count"]
        focus = options["focus"]
        season = options["season"]
        nsfw_level = options["nsfw_level"]

        favorite_motifs: List[str] = prefs.get("favorite_motifs", [])
        ng_tags: List[str] = prefs.get("ng_tags", [])

        # 1) 根據季節給一個基本場景 & mood
        season_setting, season_mood = self._season_presets(season)

        # 2) 準備 trending 裡可用的 tag（排除 NG）
        usable_trends = [t for t in trend_tags if t not in ng_tags]

        themes: List[ThemeCandidate] = []

        for i in range(count):
            # 每個主題用不同的 trending 組合一下
            extra_motifs = usable_trends[i : i + 2]  # 簡單切片（不足就短一點）

            title = self._build_title(
                season=season,
                focus=focus,
                index=i,
            )

            short_concept = self._build_short_concept(
                season_setting=season_setting,
                focus=focus,
                extra_motifs=extra_motifs,
            )

            prompt_tags = self._build_prompt_tags(
                base_template=self._get_base_prompt_template("default"),
                focus=focus,
                season_setting=season_setting,
                season_mood=season_mood,
                favorite_motifs=favorite_motifs,
                extra_motifs=extra_motifs,
            )

            theme = ThemeCandidate(
                title=title,
                short_concept=short_concept,
                prompt_tags=prompt_tags,
                nsfw_level=nsfw_level,
                meta={
                    "season": season,
                    "platform": options["platform"],
                    "source": "rule_based",
                    "extra_motifs": extra_motifs,
                },
            )
            themes.append(theme)

        return themes

    # ========= 小工具們 ========= #

    def _season_presets(self, season: str) -> tuple[str, List[str]]:
        """
        根據季節選一個基本場景（setting tag）和 mood tag。
        """
        season = (season or "any").lower()

        if season == "summer":
            return "beach", ["sunny", "bright", "relaxed"]
        if season == "spring":
            return "park_with_cherry_blossoms", ["soft", "romantic"]
        if season == "autumn":
            return "street_with_fallen_leaves", ["nostalgic", "warm"]
        if season == "winter":
            return "snowy_city", ["cozy", "quiet"]
        # default
        return "room_in_daylight", ["calm", "daily_life"]

    def _get_base_prompt_template(self, template_name: str) -> PromptTags:
        """
        從 PromptTemplateLibrary 拿 base template，
        如果沒有提供，就用一個最基本的。
        """
        if self._prompt_templates is not None:
            return self._prompt_templates.get_base_template(template_name)

        # fallback：最簡單的分類框架
        return {
            "clothing": [],
            "mood": [],
            "setting": [],
            "expression": [],
            "action": [],
            "artistic": [],
            "object": [],
        }

    def _build_title(self, season: str, focus: str, index: int) -> str:
        """
        產生主題標題（之後你可以改成更二次元風 / 加日文）。
        """
        safe_season = season or "any"

        season_str = season.capitalize() if season != "any" else "Daily"
        idx = index + 1

        if "bikini" in focus or "swimsuit" in focus:
            return f"{season_str} Beach {idx} — {focus}"
        if "uniform" in focus:
            return f"{season_str} Campus {idx} — {focus}"
        return f"{season_str} Scene {idx} — {focus}"

    def _build_short_concept(
        self,
        season_setting: str,
        focus: str,
        extra_motifs: List[str],
    ) -> str:
        """
        用一句話描述概念，方便你看列表就知道畫什麼。
        """
        motifs_str = ", ".join(extra_motifs) if extra_motifs else ""
        base = f"{season_setting.replace('_', ' ')} with {focus}"
        if motifs_str:
            return f"{base}, plus {motifs_str}"
        return base

    def _build_prompt_tags(
        self,
        base_template: PromptTags,
        focus: str,
        season_setting: str,
        season_mood: List[str],
        favorite_motifs: List[str],
        extra_motifs: List[str],
    ) -> PromptTags:
        """
        把各種元素塞進分類好的 tag 結構。
        """
        tags = {k: list(v) for k, v in base_template.items()}  # shallow copy

        # clothing：focus + 常用 motif
        clothing: List[str] = tags.get("clothing", [])
        clothing.append(focus)
        clothing.extend([m for m in favorite_motifs if m not in clothing])

        # mood
        mood_tags: List[str] = tags.get("mood", [])
        mood_tags.extend(season_mood)

        # setting
        setting_tags: List[str] = tags.get("setting", [])
        setting_tags.append(season_setting)

        # expression：先給幾個常用的
        expression_tags: List[str] = tags.get("expression", [])
        if not expression_tags:
            expression_tags.extend(["smile", "blush"])

        # action：先給你常畫的基本動作（之後可以根據主題改）
        action_tags: List[str] = tags.get("action", [])
        if not action_tags:
            action_tags.append("looking_at_viewer")

        # object：放幾個 extra motif 當小道具
        object_tags: List[str] = tags.get("object", [])
        object_tags.extend(extra_motifs)

        # artistic：可以放「high_detail」「soft_lighting」等（先留空或簡單填）
        artistic_tags: List[str] = tags.get("artistic", [])
        if not artistic_tags:
            artistic_tags.extend(["masterpiece", "best_quality", "soft_lighting"])

        # 回寫
        tags["clothing"] = list(dict.fromkeys(clothing))
        tags["mood"] = list(dict.fromkeys(mood_tags))
        tags["setting"] = list(dict.fromkeys(setting_tags))
        tags["expression"] = list(dict.fromkeys(expression_tags))
        tags["action"] = list(dict.fromkeys(action_tags))
        tags["object"] = list(dict.fromkeys(object_tags))
        tags["artistic"] = list(dict.fromkeys(artistic_tags))

        return tags

    def _build_prompt_tags_from_keywords(
        self,
        focus: str,
        season: str,
        keywords: List[str],
        mood: List[str],
    ) -> PromptTags:
        """
        提供給 LLM 版用：把 LLM 回傳的 keywords 粗略分配到各個欄位。
        目前實作很簡單，以後你可以改成更聰明的 mapping。
        """
        base = self._get_base_prompt_template("default")
        tags = {k: list(v) for k, v in base.items()}

        # focus 一樣先放 clothing
        tags["clothing"].append(focus)

        for kw in keywords:
            k = kw.lower()
            if "bikini" in k or "swimsuit" in k or "uniform" in k:
                tags["clothing"].append(kw)
            elif "beach" in k or "street" in k or "room" in k or "stage" in k:
                tags["setting"].append(kw)
            elif "cat_ears" in k or "ribbon" in k or "accessory" in k:
                tags["object"].append(kw)
            else:
                # 暫時丟到 object
                tags["object"].append(kw)

        tags["mood"].extend(mood)

        # season 也簡單轉一下 setting
        if season and season != "any":
            tags["setting"].append(season)

        return self._build_prompt_tags(
            base_template=tags,
            focus=focus,
            season_setting=self._season_presets(season)[0],
            season_mood=self._season_presets(season)[1],
            favorite_motifs=[],
            extra_motifs=[],
        )

    def _theme_to_dict(self, theme: ThemeCandidate) -> Dict[str, Any]:
        """
        統一輸出格式用 dict（方便 JSON / 存 DB / 傳給 PostWriterAgent）。
        """
        d = asdict(theme)
        # 確保 meta 至少是 {}
        if d["meta"] is None:
            d["meta"] = {}
        return d
