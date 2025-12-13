from __future__ import annotations

from typing import Dict, List


PromptTags = Dict[str, List[str]]


class SimplePromptTemplateLibrary:
    """
    最簡單可用的 Prompt Template Library。

    功能：
    - 根據 template_name 回傳一個「分類好的 Danbooru 風 tag 結構」
    - 分類欄位固定：clothing / mood / setting / expression / action / artistic / object
    - 你可以在這裡預先放一些「常用場景」的基礎 tag，ThemeAgent 再往裡面塞 focus、季節等。

    說明：
    - 如果找不到指定的 template_name，會退回 "default"
    - default 只放非常通用的 tag，方便你再疊加
    """

    def __init__(self) -> None:
        # key: template_name
        self._templates: Dict[str, PromptTags] = {}
        self._register_default_templates()

    # ========= 對外介面 ========= #

    def get_base_template(self, template_name: str) -> PromptTags:
        """
        取得指定模板的基礎 PromptTags。
        如果沒有，回傳 default。

        回傳值會是「深拷貝安全版本」，避免呼叫端改動到內部樣板。
        """
        name = (template_name or "default").lower()
        if name not in self._templates:
            name = "default"

        base = self._templates[name]

        # 深拷貝，避免外部修改到樣板
        return {k: list(v) for k, v in base.items()}

    # ========= 內部：註冊樣板 ========= #

    def _register_default_templates(self) -> None:
        """
        註冊幾個常用場景的樣板：
        - default         : 通用二次元美少女
        - swimsuit        : 泳裝 / 海邊 / 夏天
        - school_uniform  : 制服 / 校園
        - idol_stage      : 偶像舞台 / Spotlight
        - room_morning    : 早晨房間（日常 / 可愛）
        """

        # ---- default: 通用二次元美少女 ----
        self._templates["default"] = {
            "clothing": [
                # 讓 ThemeAgent 之後填 focus
            ],
            "mood": [
                "cute",
                "soft",
            ],
            "setting": [
                # 由 ThemeAgent 決定：room / street / beach ...
            ],
            "expression": [
                "smile",
                "blush",
            ],
            "action": [
                "looking_at_viewer",
            ],
            "artistic": [
                "masterpiece",
                "best_quality",
                "high_resolution",
                "detailed_eyes",
                "soft_lighting",
            ],
            "object": [
                # 小道具由 ThemeAgent/keywords 補
            ],
        }

        # ---- swimsuit: 海邊泳裝（frilled_bikini 族群） ----
        self._templates["swimsuit"] = {
            "clothing": [
                "swimsuit",
                "bikini",
                # ThemeAgent 會再塞 frilled_bikini 等更具體的
            ],
            "mood": [
                "bright",
                "relaxed",
                "summer",
            ],
            "setting": [
                "beach",
                "sea",
                "blue_sky",
            ],
            "expression": [
                "smile",
                "blush",
            ],
            "action": [
                "standing",
                "looking_at_viewer",
            ],
            "artistic": [
                "masterpiece",
                "best_quality",
                "high_resolution",
                "detailed_water",
                "sunlight",
                "backlighting",
            ],
            "object": [
                "waves",
                "sand",
            ],
        }

        # ---- school_uniform: 校園制服 ----
        self._templates["school_uniform"] = {
            "clothing": [
                "school_uniform",
                "pleated_skirt",
                "blazer",
            ],
            "mood": [
                "daily_life",
                "youthful",
                "soft",
            ],
            "setting": [
                "school_hallway",
                "classroom",
            ],
            "expression": [
                "smile",
                "blush",
            ],
            "action": [
                "walking",
                "looking_at_viewer",
            ],
            "artistic": [
                "masterpiece",
                "best_quality",
                "high_resolution",
                "soft_lighting",
            ],
            "object": [
                "school_bag",
                "windows",
            ],
        }

        # ---- idol_stage: 偶像舞台 ----
        self._templates["idol_stage"] = {
            "clothing": [
                "idol_costume",
                "frills",
                "ribbons",
            ],
            "mood": [
                "energetic",
                "sparkling",
                "stage_performance",
            ],
            "setting": [
                "stage",
                "spotlight",
                "audience_in_background",
            ],
            "expression": [
                "smile",
                "winking",
            ],
            "action": [
                "singing",
                "dancing",
                "holding_microphone",
            ],
            "artistic": [
                "masterpiece",
                "best_quality",
                "high_resolution",
                "dynamic_lighting",
                "colorful_lights",
            ],
            "object": [
                "microphone",
                "stage_lights",
                "confetti",
            ],
        }

        # ---- room_morning: 早晨房間（日常） ----
        self._templates["room_morning"] = {
            "clothing": [
                "casual_outfit",
                "roomwear",
            ],
            "mood": [
                "cozy",
                "relaxed",
                "morning",
            ],
            "setting": [
                "bedroom",
                "sunlight_through_window",
            ],
            "expression": [
                "sleepy_eyes",
                "small_smile",
            ],
            "action": [
                "stretching",
                "sitting_on_bed",
            ],
            "artistic": [
                "masterpiece",
                "best_quality",
                "soft_lighting",
                "warm_tones",
            ],
            "object": [
                "pillow",
                "blanket",
                "plush_toy",
            ],
        }


__all__ = ["SimplePromptTemplateLibrary"]
