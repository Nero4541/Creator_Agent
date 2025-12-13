from __future__ import annotations

from typing import Dict, List, Tuple
import random
import datetime as _dt


class SimpleTrendFetcher:
    """
    簡易版 TrendFetcher：
    - 不連網、不爬蟲，完全用手動維護的熱門 tag 池
    - 依 category（目前主要是 "anime"）＋季節，回傳一組 trending tags
    - ThemeAgent 只會用 get_trending_tags(...) 這個介面

    之後如果你要接：
    - X / Twitter API
    - Pixiv 排行
    - 自己的作品資料庫

    只要改這個 class 或再寫一個新的 TrendFetcher 實作即可。
    """

    def __init__(self) -> None:
        # 主分類 → tag 池
        self._base_pools: Dict[str, List[str]] = {}
        # (category, season) → tag 池
        self._seasonal_pools: Dict[Tuple[str, str], List[str]] = {}

        self._register_default_pools()

    # ========= 公開介面 ========= #

    def get_trending_tags(
        self,
        category: str = "anime",
        limit: int = 20,
    ) -> List[str]:
        """
        回傳近期熱門 tag（假資料版）。

        目前策略：
        1. 根據 category 拿 base pool
        2. 根據推測季節附加 seasonal pool
        3. 打散順序
        4. 回傳最多 limit 個（去重）

        Args:
            category: 目前主要用 "anime"
            limit:    希望回傳的最大數量

        Returns:
            List[str]: 不重複的 tag 列表
        """
        category = category.lower()
        if limit <= 0:
            return []

        base = list(self._base_pools.get(category, []))

        # 用當前月份推一個季節，用來混 seasonal tags
        season = self._infer_season()
        seasonal = list(self._seasonal_pools.get((category, season), []))

        combined = base + seasonal

        # 去重保持原順序
        seen = set()
        uniq: List[str] = []
        for t in combined:
            if t not in seen:
                seen.add(t)
                uniq.append(t)

        # 打散順序（讓每次主題看起來有點不同）
        random.shuffle(uniq)

        return uniq[:limit]

    # ========= 內部：註冊預設 tag 池 ========= #

    def _register_default_pools(self) -> None:
        """
        手動登錄一些常見二次元熱門 tag。
        你可以依自己口味修改／增加。
        """

        # ---- 通用 anime 類別 ----
        self._base_pools["anime"] = [
            # 角色／造型類
            "twintails",
            "side_ponytail",
            "long_hair",
            "short_hair",
            "ahoge",
            "hair_ribbon",
            "hairband",
            "cat_ears",
            "animal_ears",

            # 服裝類
            "school_uniform",
            "sailor_uniform",
            "serafuku",
            "hoodie",
            "jacket",
            "idol_costume",
            "onepiece",
            "thighhighs",
            "knee_socks",
            "bare_legs",

            # 氣氛／構圖
            "smile",
            "blush",
            "sidelong_glance",
            "looking_at_viewer",
            "waving",
            "peace_sign",
            "winking",

            # 場景
            "street",
            "school_hallway",
            "classroom",
            "bedroom",
            "rooftop",
            "stage",
            "city_lights",

            # 畫面風格
            "soft_lighting",
            "backlighting",
            "bokeh",
            "lens_flare",
            "sparkles",
        ]

        # ---- seasonal：anime + summer ----
        self._seasonal_pools[("anime", "summer")] = [
            "frilled_bikini",
            "bikini",
            "swimsuit",
            "school_swimsuit",
            "sarong",
            "sunhat",
            "sunglasses",
            "beach",
            "sea",
            "waves",
            "sand",
            "sunset",
            "blue_sky",
            "water_drops",
            "ice_cream",
            "ramune",
            "festival",
            "yukata",
            "fireworks",
        ]

        # ---- seasonal：anime + spring ----
        self._seasonal_pools[("anime", "spring")] = [
            "sakura",
            "cherry_blossoms",
            "flower_petals",
            "park",
            "spring_dress",
            "cardigan",
            "light_scarf",
            "breeze",
            "soft_colors",
        ]

        # ---- seasonal：anime + autumn ----
        self._seasonal_pools[("anime", "autumn")] = [
            "fallen_leaves",
            "autumn_leaves",
            "coat",
            "scarf",
            "beret",
            "coffee",
            "cafe",
            "sunset_street",
            "warm_colors",
        ]

        # ---- seasonal：anime + winter ----
        self._seasonal_pools[("anime", "winter")] = [
            "coat",
            "scarf",
            "mittens",
            "boots",
            "turtleneck",
            "snow",
            "snowflakes",
            "winter_city",
            "breath_visible",
            "warm_drink",
        ]

    # ========= 內部：推斷季節 ========= #

    def _infer_season(self) -> str:
        """
        用當前月份簡單推一個季節。
        你如果想改成「從 payload 傳入 season」，
        可以把這邊改成參數化。
        """
        month = _dt.datetime.now().month

        if month in (12, 1, 2):
            return "winter"
        if month in (3, 4, 5):
            return "spring"
        if month in (6, 7, 8):
            return "summer"
        return "autumn"


__all__ = ["SimpleTrendFetcher"]
