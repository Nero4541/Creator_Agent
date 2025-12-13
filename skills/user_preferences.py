from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from agents.post_writer_agent import CaptionStyle


class SimpleUserPreferenceStore:
    """
    管理「主題／畫面」相關的偏好設定，給 ThemeAgent 使用。

    目前設計成：全部 configuration 寫在程式內，
    之後你要改成讀 YAML / JSON / 環境變數都可以在這裡動手。
    """

    def __init__(self) -> None:
        # 這裡是「預設偏好」，你可以直接改成你自己的口味
        self._prefs: Dict[str, Any] = {
            "default_style": "anime_girl",
            "allowed_nsfw_level": "sfw",   # 之後你要開 mild / nsfw 可以在這裡改
            "favorite_motifs": [
                "frilled_bikini",
                "school_uniform",
                "thighhighs",
                "bare_legs",
                "side_ponytail",
                "twin_tails",
                "idol_costume",
            ],
            "ng_tags": [
                "gore",
                "violence",
                "blood",
                "guts",
                "extreme_guro",
            ],
            # 對某些 focus 給預設 template 提示（ThemeAgent 目前沒強用，但你之後可以接）
            "focus_template_map": {
                "bikini": "swimsuit",
                "swimsuit": "swimsuit",
                "frilled_bikini": "swimsuit",
                "school_uniform": "school_uniform",
                "idol": "idol_stage",
                "idol_costume": "idol_stage",
                "room_morning": "room_morning",
            },
        }

    # ====== ThemeAgent 會呼叫的介面 ====== #

    def get_theme_preferences(self) -> Dict[str, Any]:
        """
        目前 ThemeAgent 只需要這個 method：
        回傳一個 dict，內容可以包含：
        - default_style: str
        - allowed_nsfw_level: str
        - favorite_motifs: List[str]
        - ng_tags: List[str]
        - focus_template_map: Dict[str, str]
        """
        # 回傳 shallow copy，避免外部直接改到內部 dict
        return dict(self._prefs)

    # ====== 如果你將來要改偏好可以加 helper ====== #

    def set_allowed_nsfw_level(self, level: str) -> None:
        self._prefs["allowed_nsfw_level"] = level

    def add_favorite_motif(self, tag: str) -> None:
        if tag not in self._prefs["favorite_motifs"]:
            self._prefs["favorite_motifs"].append(tag)

    def add_ng_tag(self, tag: str) -> None:
        if tag not in self._prefs["ng_tags"]:
            self._prefs["ng_tags"].append(tag)


class SimplePostStylePreferenceStore:
    """
    管理「貼文風格」相關的預設選項，給 PostWriterAgent 使用。

    例：
    - X 日文：預設 cute 語氣
    - X 中文：預設 cute 語氣
    - Patreon：預設 patreon_support 語氣
    """

    def __init__(self) -> None:
        # key: (platform, language) → CaptionStyle
        # 一律轉小寫後使用
        self._styles: Dict[tuple[str, str], CaptionStyle] = {}

        self._register_default_styles()

    def _register_default_styles(self) -> None:
        # X / Twitter：日文 → 可愛語氣
        self._styles[("x", "ja")] = CaptionStyle(tone="cute")
        self._styles[("twitter", "ja")] = CaptionStyle(tone="cute")

        # X / Twitter：中文 → 可愛語氣
        self._styles[("x", "zh")] = CaptionStyle(tone="cute")
        self._styles[("twitter", "zh")] = CaptionStyle(tone="cute")
        self._styles[("x", "zh-tw")] = CaptionStyle(tone="cute")
        self._styles[("twitter", "zh-tw")] = CaptionStyle(tone="cute")

        # Patreon：日文／中文 → 支持向語氣
        self._styles[("patreon", "ja")] = CaptionStyle(tone="patreon_support")
        self._styles[("patreon", "zh")] = CaptionStyle(tone="patreon_support")
        self._styles[("patreon", "zh-tw")] = CaptionStyle(tone="patreon_support")

        # Pixiv：日文 → 比較普通／serious
        self._styles[("pixiv", "ja")] = CaptionStyle(tone="serious")

    # ====== PostWriterAgent 會呼叫的介面 ====== #

    def get_default_style(
        self,
        platform: str,
        language: str,
    ) -> CaptionStyle:
        """
        回傳預設的 CaptionStyle。
        找不到就給一個 cute 當通用 fallback。
        """
        p = platform.lower()
        if p == "twitter":
            p = "x"
        lang = language.lower()

        style = self._styles.get((p, lang))
        if style is not None:
            # 回傳一個新實例，避免外面改到原本的
            return CaptionStyle(**asdict(style))

        # fallback：用可愛語氣
        return CaptionStyle(tone="cute")


__all__ = [
    "SimpleUserPreferenceStore",
    "SimplePostStylePreferenceStore",
]
