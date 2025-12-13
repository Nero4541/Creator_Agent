from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
import uuid


# ========= 共用型別 ========= #

Platform = Literal["x", "twitter", "pixiv", "patreon", "booth", "other"]
LanguageCode = Literal["ja", "zh", "zh-tw", "en", "other"]
NsfwLevel = Literal["sfw", "mild", "nsfw"]


def _gen_id() -> str:
    return str(uuid.uuid4())


def _utc_now() -> datetime:
    return datetime.utcnow()


# ========= ThemeRecord：主題資料 ========= #

@dataclass
class ThemeRecord:
    """
    用來儲存 ThemeAgent 產生的主題。

    一般流程：
    - ThemeAgent 產生一組主題（title / short_concept / prompt_tags / meta）
    - 你可以把它們轉成 ThemeRecord 後存 DB / JSON

    對應欄位：
    - id           : 主鍵
    - created_at   : 建立時間（UTC）
    - title        : 主題標題
    - short_concept: 一句話概念描述
    - prompt_tags  : Danbooru 風分類 tags (clothing/mood/setting/...)
    - nsfw_level   : "sfw" / "mild" / "nsfw"
    - meta         : 其他額外資訊（season/platform/source/...）
    - used_count   : 被用來畫圖／發文的次數
    """

    title: str
    short_concept: str
    prompt_tags: Dict[str, List[str]]

    id: str = field(default_factory=_gen_id)
    created_at: datetime = field(default_factory=_utc_now)
    nsfw_level: NsfwLevel = "sfw"
    meta: Dict[str, Any] = field(default_factory=dict)
    used_count: int = 0

    @classmethod
    def from_theme_dict(cls, data: Dict[str, Any]) -> "ThemeRecord":
        """
        方便直接接 ThemeAgent 輸出的 dict：

        theme_dict = {
            "title": ...,
            "short_concept": ...,
            "prompt_tags": {...},
            "nsfw_level": "sfw",
            "meta": {...}
        }
        """
        return cls(
            title=data.get("title", "Untitled Theme"),
            short_concept=data.get("short_concept", ""),
            prompt_tags=data.get("prompt_tags") or {},
            nsfw_level=data.get("nsfw_level", "sfw"),
            meta=data.get("meta") or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ========= ArtworkRecord：作品資料 ========= #

@dataclass
class ArtworkRecord:
    """
    用來描述一張實際輸出的圖片／作品。

    你可以用它來記錄：
    - 是從哪個 ThemeRecord 來的
    - 圖檔實際存在哪（本機路徑 / URL / 雲端 key）
    - 與畫面相關的 meta（角色名、使用的模型、seed 等）

    欄位：
    - id            : 主鍵
    - created_at    : 建立時間（UTC）
    - theme_id      : 來源主題（可選）
    - title         : 作品標題（通常沿用 theme.title 或你自訂）
    - image_path    : 檔案路徑 or URL
    - prompt_tags   : 實際生成時用的 tags（可選，方便回溯）
    - meta          : 其他資訊（model_name, seed, sampler, cfg_scale...）
    """

    title: str
    image_path: str

    id: str = field(default_factory=_gen_id)
    created_at: datetime = field(default_factory=_utc_now)

    theme_id: Optional[str] = None
