from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from app.orchestrator import AgentResponse, PostWriterAgentProtocol


# =========================
# 型別 & Protocol 定義
# =========================

@dataclass
class CaptionStyle:
    """
    控制文案風格的設定。

    tone:
        - "cute"
        - "cool"
        - "serious"
        - "patreon_support"
        等等，你可以之後再擴充。
    """
    tone: str = "cute"
    # 之後如果要加「第一人稱／第三人稱」、「敬語／隨便」也可以放進來。


@runtime_checkable
class CaptionTemplateLibraryProtocol(Protocol):
    """
    提供平台＋語言＋語氣對應的文案模板。
    模板裡可以有 {title} {mood} {characters} {extra} {hashtags} 等 placeholder。
    """

    def get_caption_template(
        self,
        platform: str,
        language: str,
        tone: str,
    ) -> str:
        ...


@runtime_checkable
class HashtagGeneratorProtocol(Protocol):
    """
    專門負責 hashtag 生成，可以根據作品 meta + 平台 + 語言。
    """

    def generate_hashtags(
        self,
        artwork_meta: Dict[str, Any],
        platform: str,
        language: str,
        max_count: int = 5,
    ) -> List[str]:
        ...


@runtime_checkable
class PostStylePreferenceStoreProtocol(Protocol):
    """
    儲存你對「文案風格」的偏好，例如：
    - X 一律可愛語氣
    - Patreon 比較感謝／支持向
    """

    def get_default_style(
        self,
        platform: str,
        language: str,
    ) -> CaptionStyle:
        ...


# =========================
# PostWriterAgent 實作
# =========================

class PostWriterAgent(PostWriterAgentProtocol):
    """
    負責：
    - 根據作品 meta 生成多語言貼文（X / Patreon / Pixiv 等）
    - 控制語氣、長度、emoji 使用等
    """

    def __init__(
        self,
        caption_templates: CaptionTemplateLibraryProtocol,
        style_prefs: PostStylePreferenceStoreProtocol,
        hashtag_generator: Optional[HashtagGeneratorProtocol] = None,
    ) -> None:
        # 這兩個在正式環境必須提供
        self._caption_templates = caption_templates
        self._style_prefs = style_prefs
        # hashtag_generator 是可選的；若未提供，使用內建規則生成
        self._hashtag_generator = hashtag_generator

    # ========= Orchestrator 入口 ========= #

    def handle(self, payload: Dict[str, Any]) -> AgentResponse:
        """
        payload 期待的欄位（目前版本）：
        - platform: "X" / "Patreon" / "Pixiv" ...
        - languages: ["ja", "zh", "en", ...]
        - artwork_meta: {
              "title": str,
              "mood": str,
              "theme_tags": list[str],
              "characters": list[str],
              "special_note": str,
              ...
          }
        - style: （可選）覆寫風格設定，例如 {"tone": "serious"}
        """
        try:
            options = self._normalize_payload(payload)
            platform = options["platform"]
            languages = options["languages"]
            artwork_meta = options["artwork_meta"]
            style_override = options["style"]

            posts: Dict[str, str] = {}

            for lang in languages:
                style = self._resolve_style(platform, lang, style_override)
                hashtags = self._generate_hashtags(artwork_meta, platform, lang)
                caption = self._build_caption(
                    platform=platform,
                    language=lang,
                    artwork_meta=artwork_meta,
                    style=style,
                    hashtags=hashtags,
                )
                posts[lang] = caption

            return AgentResponse(ok=True, data={"posts": posts})

        except Exception as e:
            return AgentResponse(
                ok=False,
                data=None,
                error=f"PostWriterAgent error: {e}",
            )

    # ========= Payload 處理 ========= #

    def _normalize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        整理 payload ＋ 預設值，避免 KeyError。
        """
        platform = payload.get("platform", "X")
        languages = payload.get("languages") or ["ja"]

        artwork_meta = payload.get("artwork_meta") or {}

        # style override（可選）
        style_raw = payload.get("style") or {}
        style = CaptionStyle(
            tone=style_raw.get("tone", "cute"),
        )

        return {
            "platform": platform,
            "languages": languages,
            "artwork_meta": artwork_meta,
            "style": style,
        }

    # ========= 風格設定 ========= #

    def _resolve_style(
        self,
        platform: str,
        language: str,
        override: CaptionStyle,
    ) -> CaptionStyle:
        """
        先看有沒有偏好設定，再用 override 蓋掉。
        """
        base_style = self._style_prefs.get_default_style(platform, language)

        if override.tone:
            base_style.tone = override.tone

        return base_style

    # ========= Hashtag 生成 ========= #

    def _generate_hashtags(
        self,
        artwork_meta: Dict[str, Any],
        platform: str,
        language: str,
    ) -> List[str]:
        """
        若提供 HashtagGenerator，則委派；
        否則用正式的內建規則：
        - 依語言加 AI 插畫類型 tag
        - 依平台加平台 tag
        - 適度使用 theme_tags
        """
        if self._hashtag_generator is not None:
            return self._hashtag_generator.generate_hashtags(
                artwork_meta=artwork_meta,
                platform=platform,
                language=language,
                max_count=5,
            )

        theme_tags: List[str] = artwork_meta.get("theme_tags") or []
        base_tags: List[str] = []

        # 作品類型（語言別）
        if language == "ja":
            base_tags.append("AIイラスト")
        elif language in ("zh", "zh-tw"):
            base_tags.append("AI插畫")
        else:
            base_tags.append("ai_art")

        # 平台 tag
        p = platform.lower()
        if p in ("x", "twitter"):
            base_tags.append("AIart")
        elif p == "patreon":
            base_tags.append("Patreon")

        # 從 theme_tags 抽幾個
        for t in theme_tags[:3]:
            base_tags.append(t)

        # 去重
        seen = set()
        uniq = []
        for t in base_tags:
            if t not in seen:
                seen.add(t)
                uniq.append(t)

        return uniq

    # ========= Caption 建構 ========= #

    def _build_caption(
        self,
        platform: str,
        language: str,
        artwork_meta: Dict[str, Any],
        style: CaptionStyle,
        hashtags: List[str],
    ) -> str:
        """
        依平台 & 語言 & 風格生成實際貼文。
        優先使用 CaptionTemplateLibrary，沒有模板時使用語言別預設格式。
        """
        title = artwork_meta.get("title", "Untitled")
        mood = artwork_meta.get("mood", "")
        special_note = artwork_meta.get("special_note", "")
        characters = artwork_meta.get("characters") or []

        char_str = self._build_character_str(characters, language)
        extra_line = self._build_extra_line(special_note, language)
        hashtag_line = self._format_hashtags(hashtags)

        if self._caption_templates is not None:
            template = self._caption_templates.get_caption_template(
                platform=platform,
                language=language,
                tone=style.tone,
            )
            return template.format(
                title=title,
                mood=mood,
                characters=char_str,
                extra=extra_line,
                hashtags=hashtag_line,
            )

        # 沒有 template：語言別預設正式格式
        if language == "ja":
            return self._build_caption_ja(
                platform=platform,
                title=title,
                mood=mood,
                char_str=char_str,
                extra_line=extra_line,
                hashtags_line=hashtag_line,
                style=style,
            )
        elif language in ("zh", "zh-tw"):
            return self._build_caption_zh(
                platform=platform,
                title=title,
                mood=mood,
                char_str=char_str,
                extra_line=extra_line,
                hashtags_line=hashtag_line,
                style=style,
            )
        else:
            return self._build_caption_en(
                platform=platform,
                title=title,
                mood=mood,
                char_str=char_str,
                extra_line=extra_line,
                hashtags_line=hashtag_line,
                style=style,
            )

    # ========= 語言別預設實作 ========= #

    def _build_caption_ja(
        self,
        platform: str,
        title: str,
        mood: str,
        char_str: str,
        extra_line: str,
        hashtags_line: str,
        style: CaptionStyle,
    ) -> str:
        """
        日文版預設：可愛系 X 用語。
        """
        lines: List[str] = []

        if style.tone == "cute":
            lines.append(f"{title} を描きました🎨✨")
        elif style.tone == "serious":
            lines.append(f"新作イラスト「{title}」です。")
        elif style.tone == "patreon_support":
            lines.append(f"「{title}」が完成しました、いつも応援ありがとうございます🎨")
        else:
            lines.append(f"{title} 完成しました。")

        if char_str:
            lines.append(char_str)
        if mood:
            lines.append(mood)
        if extra_line:
            lines.append(extra_line)

        if hashtags_line:
            lines.append("")
            lines.append(hashtags_line)

        text = "\n".join(l for l in lines if l != "" or hashtags_line)

        if platform.lower() in ("x", "twitter") and len(text) > 260:
            text = text[:257] + "…"

        return text

    def _build_caption_zh(
        self,
        platform: str,
        title: str,
        mood: str,
        char_str: str,
        extra_line: str,
        hashtags_line: str,
        style: CaptionStyle,
    ) -> str:
        """
        中文版預設：輕鬆可愛口吻（偏繁中）。
        """
        lines: List[str] = []

        if style.tone == "cute":
            lines.append(f"新畫好了《{title}》🎨✨")
        elif style.tone == "serious":
            lines.append(f"這次的作品是《{title}》。")
        elif style.tone == "patreon_support":
            lines.append(f"《{title}》完成了，謝謝一直支持的你們🎨")
        else:
            lines.append(f"完成一張新圖：《{title}》。")

        if char_str:
            lines.append(char_str)
        if mood:
            lines.append(mood)
        if extra_line:
            lines.append(extra_line)

        if hashtags_line:
            lines.append("")
            lines.append(hashtags_line)

        text = "\n".join(l for l in lines if l != "" or hashtags_line)

        if platform.lower() in ("x", "twitter") and len(text) > 260:
            text = text[:257] + "…"

        return text

    def _build_caption_en(
        self,
        platform: str,
        title: str,
        mood: str,
        char_str: str,
        extra_line: str,
        hashtags_line: str,
        style: CaptionStyle,
    ) -> str:
        """
        英文版預設：通用 SNS 友善文案。
        """
        lines: List[str] = []

        if style.tone == "cute":
            lines.append(f"Finished a new piece: “{title}” 🎨✨")
        elif style.tone == "serious":
            lines.append(f"My new illustration: “{title}”.")
        elif style.tone == "patreon_support":
            lines.append(f"“{title}” is done, thank you for your support as always 🎨")
        else:
            lines.append(f"New artwork: “{title}”.")

        if char_str:
            lines.append(char_str)
        if mood:
            lines.append(mood)
        if extra_line:
            lines.append(extra_line)

        if hashtags_line:
            lines.append("")
            lines.append(hashtags_line)

        text = "\n".join(l for l in lines if l != "" or hashtags_line)

        if platform.lower() in ("x", "twitter") and len(text) > 260:
            text = text[:257] + "…"

        return text

    # ========= 小工具 ========= #

    def _build_character_str(
        self,
        characters: List[str],
        language: str,
    ) -> str:
        if not characters:
            return ""

        if language == "ja":
            if len(characters) == 1:
                return f"今回の主役は {characters[0]} です。"
            return f"{'、'.join(characters)} たちとの一枚です。"
        elif language in ("zh", "zh-tw"):
            if len(characters) == 1:
                return f"這次的主角是 {characters[0]}。"
            return f"這次是一張和 {'、'.join(characters)} 的合照。"
        else:
            if len(characters) == 1:
                return f"Starring {characters[0]}."
            return f"Featuring {' & '.join(characters)}."

    def _build_extra_line(self, special_note: str, language: str) -> str:
        if not special_note:
            return ""
        return special_note

    def _format_hashtags(self, hashtags: List[str]) -> str:
        if not hashtags:
            return ""
        return " ".join(f"#{tag}" for tag in hashtags)
