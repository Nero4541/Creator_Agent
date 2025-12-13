from __future__ import annotations

from typing import Dict, Tuple


class SimpleCaptionTemplateLibrary:
    """
    最簡單可用的 Caption Template Library。

    功能：
    - 根據 (platform, language, tone) 回傳一個字串模板
    - 模板內可用的 placeholder：
        {title}      - 作品標題
        {mood}       - 氣氛、情緒描述
        {characters} - 角色說明（可空字串）
        {extra}      - 特別備註（可空字串）
        {hashtags}   - hashtag 整行（已經組好）

    說明：
    - 如果找不到完全匹配的模板，會自動用「tone=fallback」或「tone=cute」退而求其次
    - 你可以自己往下加更多 key，例如:
        ("x", "ja", "cool")
        ("pixiv", "ja", "cute")
        ...
    """

    def __init__(self) -> None:
        # key: (platform, language, tone)
        # platform / language / tone 一律用小寫
        self._templates: Dict[Tuple[str, str, str], str] = {}

        self._register_default_templates()

    # ========= 對外介面 ========= #

    def get_caption_template(
        self,
        platform: str,
        language: str,
        tone: str,
    ) -> str:
        """
        取得對應平台＋語言＋語氣的模板。

        若找不到完全匹配，會依序嘗試：
        1. (platform, language, tone)
        2. (platform, language, "cute")    # 同平台語言的可愛語氣
        3. (platform, language, "fallback")
        4. ("*", language, tone)
        5. ("*", language, "cute")
        6. ("*", language, "fallback")

        最後若仍找不到，給一個非常通用的英文 fallback。
        """
        p = platform.lower()
        if p == "twitter":
            p = "x"
        lang = language.lower()
        t = tone.lower()

        # 依序嘗試不同 key
        candidates = [
            (p, lang, t),
            (p, lang, "cute"),
            (p, lang, "fallback"),
            ("*", lang, t),
            ("*", lang, "cute"),
            ("*", lang, "fallback"),
        ]

        for key in candidates:
            if key in self._templates:
                return self._templates[key]

        # 萬一什麼都沒有，最後保底
        return (
            "{title}\n"
            "{characters}\n"
            "{mood}\n"
            "{extra}\n\n"
            "{hashtags}"
        )

    # ========= 內部：預設模板註冊 ========= #

    def _register_default_templates(self) -> None:
        """
        註冊幾組預設模板：
        - X / 日文 / 可愛
        - X / 中文 / 可愛
        - X / 日文 / 認真
        - X / 中文 / 認真
        - Patreon / 日文 / support
        - Patreon / 中文 / support
        - 通用 fallback
        """

        # --- X（Twitter）: 日文，可愛語氣 ---
        self._templates[("x", "ja", "cute")] = (
            "{title} を描きました🎨✨\n"
            "{characters}\n"
            "{mood}\n"
            "{extra}\n"
            "\n"
            "{hashtags}"
        )

        # --- X: 中文，可愛語氣（預設繁中）---
        self._templates[("x", "zh", "cute")] = (
            "新畫好了《{title}》🎨✨\n"
            "{characters}\n"
            "{mood}\n"
            "{extra}\n"
            "\n"
            "{hashtags}"
        )
        # 若你想區分 zh-tw / zh-cn，也可以加一個 ("x", "zh-tw", "cute")

        # --- X: 日文，認真語氣 ---
        self._templates[("x", "ja", "serious")] = (
            "新作イラスト「{title}」です。\n"
            "{characters}\n"
            "{mood}\n"
            "{extra}\n"
            "\n"
            "{hashtags}"
        )

        # --- X: 中文，認真語氣 ---
        self._templates[("x", "zh", "serious")] = (
            "這次的作品是《{title}》。\n"
            "{characters}\n"
            "{mood}\n"
            "{extra}\n"
            "\n"
            "{hashtags}"
        )

        # --- Patreon: 日文，支持向語氣 ---
        self._templates[("patreon", "ja", "patreon_support")] = (
            "「{title}」が完成しました、いつも応援ありがとうございます🎨\n"
            "{characters}\n"
            "{mood}\n"
            "{extra}\n"
            "\n"
            "{hashtags}"
        )

        # --- Patreon: 中文，支持向語氣 ---
        self._templates[("patreon", "zh", "patreon_support")] = (
            "《{title}》完成了，謝謝一直支持的你們🎨\n"
            "{characters}\n"
            "{mood}\n"
            "{extra}\n"
            "\n"
            "{hashtags}"
        )

        # --- 通用日文 fallback ---
        self._templates[("*", "ja", "fallback")] = (
            "{title} を描きました。\n"
            "{characters}\n"
            "{mood}\n"
            "{extra}\n"
            "\n"
            "{hashtags}"
        )

        # --- 通用中文 fallback ---
        self._templates[("*", "zh", "fallback")] = (
            "完成一張新圖：《{title}》。\n"
            "{characters}\n"
            "{mood}\n"
            "{extra}\n"
            "\n"
            "{hashtags}"
        )

        # --- 通用英文 fallback ---
        self._templates[("*", "en", "fallback")] = (
            "New artwork: “{title}” 🎨\n"
            "{characters}\n"
            "{mood}\n"
            "{extra}\n"
            "\n"
            "{hashtags}"
        )


__all__ = ["SimpleCaptionTemplateLibrary"]
