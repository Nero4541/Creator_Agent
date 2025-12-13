# storage/repositories.py

from __future__ import annotations

from typing import Dict, List, Optional, Iterable
from datetime import datetime

from .models import (
    ThemeRecord,
    ArtworkRecord,
    PostRecord,
    Platform,
    LanguageCode,
)


class ThemeRepository:
    """
    管理 ThemeRecord 的簡易 Repository（目前為 in-memory 實作）。

    之後你要改用 DB，只要：
    - 保留這些方法的介面
    - 把內部 dict 改成 DB 查詢 / 寫入 就好
    """

    def __init__(self) -> None:
        # key: theme_id
        self._items: Dict[str, ThemeRecord] = {}

    # ===== 基本 CRUD ===== #

    def add(self, theme: ThemeRecord) -> ThemeRecord:
        self._items[theme.id] = theme
        return theme

    def get(self, theme_id: str) -> Optional[ThemeRecord]:
        return self._items.get(theme_id)

    def update(self, theme: ThemeRecord) -> None:
        if theme.id in self._items:
            self._items[theme.id] = theme

    def delete(self, theme_id: str) -> None:
        self._items.pop(theme_id, None)

    # ===== 查詢方法 ===== #

    def list_all(self) -> List[ThemeRecord]:
        return list(self._items.values())

    def list_recent(self, limit: int = 20) -> List[ThemeRecord]:
        items = sorted(
            self._items.values(),
            key=lambda x: x.created_at,
            reverse=True,
        )
        return items[:limit]

    def list_by_nsfw_level(self, nsfw_level: str) -> List[ThemeRecord]:
        return [
            t for t in self._items.values()
            if t.nsfw_level == nsfw_level
        ]

    def increment_used_count(self, theme_id: str) -> None:
        theme = self._items.get(theme_id)
        if theme is not None:
            theme.used_count += 1
            self._items[theme_id] = theme


class ArtworkRepository:
    """
    管理 ArtworkRecord 的簡易 Repository（in-memory）。

    可以用來：
    - 記錄你生成的每張圖
    - 查詢某個 theme_id 對應的所有作品
    """

    def __init__(self) -> None:
        # key: artwork_id
        self._items: Dict[str, ArtworkRecord] = {}

    # ===== 基本 CRUD ===== #

    def add(self, artwork: ArtworkRecord) -> ArtworkRecord:
        self._items[artwork.id] = artwork
        return artwork

    def get(self, artwork_id: str) -> Optional[ArtworkRecord]:
        return self._items.get(artwork_id)

    def update(self, artwork: ArtworkRecord) -> None:
        if artwork.id in self._items:
            self._items[artwork.id] = artwork

    def delete(self, artwork_id: str) -> None:
        self._items.pop(artwork_id, None)

    # ===== 查詢方法 ===== #

    def list_all(self) -> List[ArtworkRecord]:
        return list(self._items.values())

    def list_recent(self, limit: int = 20) -> List[ArtworkRecord]:
        items = sorted(
            self._items.values(),
            key=lambda x: x.created_at,
            reverse=True,
        )
        return items[:limit]

    def list_by_theme(self, theme_id: str) -> List[ArtworkRecord]:
        return [
            a for a in self._items.values()
            if a.theme_id == theme_id
        ]

    def list_by_path_prefix(self, prefix: str) -> List[ArtworkRecord]:
        """
        例如你把圖都存成 "outputs/2025-11-29/..."，
        可以用 prefix 找同一批輸出。
        """
        return [
            a for a in self._items.values()
            if a.image_path.startswith(prefix)
        ]


class PostRepository:
    """
    管理 PostRecord 的簡易 Repository（in-memory）。

    用途：
    - 記錄每張圖在哪些平台／語言發過貼文
    - 之後可以回填 performance（like/RT/收藏數）
    """

    def __init__(self) -> None:
        # key: post_id
        self._items: Dict[str, PostRecord] = {}

    # ===== 基本 CRUD ===== #

    def add(self, post: PostRecord) -> PostRecord:
        self._items[post.id] = post
        return post

    def get(self, post_id: str) -> Optional[PostRecord]:
        return self._items.get(post_id)

    def update(self, post: PostRecord) -> None:
        if post.id in self._items:
            self._items[post.id] = post

    def delete(self, post_id: str) -> None:
        self._items.pop(post_id, None)

    # ===== 查詢方法 ===== #

    def list_all(self) -> List[PostRecord]:
        return list(self._items.values())

    def list_recent(self, limit: int = 50) -> List[PostRecord]:
        items = sorted(
            self._items.values(),
            key=lambda x: x.created_at,
            reverse=True,
        )
        return items[:limit]

    def list_by_artwork(self, artwork_id: str) -> List[PostRecord]:
        return [
            p for p in self._items.values()
            if p.artwork_id == artwork_id
        ]

    def list_by_platform(
        self,
        platform: Platform,
        limit: int = 50,
    ) -> List[PostRecord]:
        p = platform
        items = [
            p_rec
            for p_rec in self._items.values()
            if p_rec.platform == p
        ]
        items.sort(key=lambda x: x.created_at, reverse=True)
        return items[:limit]

    def list_by_platform_and_language(
        self,
        platform: Platform,
        language: LanguageCode,
        limit: int = 50,
    ) -> List[PostRecord]:
        p = platform
        lang = language
        items = [
            p_rec
            for p_rec in self._items.values()
            if p_rec.platform == p and p_rec.language == lang
        ]
        items.sort(key=lambda x: x.created_at, reverse=True)
        return items[:limit]

    # ===== performance / 統計 ===== #

    def update_performance(
        self,
        post_id: str,
        performance: Dict[str, int],
    ) -> None:
        """
        更新一則貼文的表現數據，例如：
        performance = {
            "likes": 123,
            "retweets": 45,
            "bookmarks": 10,
        }
        """
        post = self._items.get(post_id)
        if post is None:
            return

        # 淺合併
        post.performance.update(performance)
        self._items[post_id] = post

    def aggregate_performance_by_artwork(
        self,
        artwork_id: str,
    ) -> Dict[str, int]:
        """
        統計同一張圖在多平台／多語言的總表現。
        回傳類似：
        {
          "likes": 300,
          "retweets": 50,
          "bookmarks": 80,
        }
        """
        totals: Dict[str, int] = {}
