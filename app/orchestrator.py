from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Protocol, runtime_checkable


# ==== 型別定義 ==== #

RequestType = Literal["generate_theme", "write_post"]


@dataclass
class AgentRequest:
    """
    系統內部統一使用的請求格式。

    例子：
    AgentRequest(
        type="generate_theme",
        payload={
            "count": 5,
            "season": "summer",
            "focus": "frilled bikini",
            "platform": "X",
            "nsfw_level": "sfw",
        },
    )
    """
    type: RequestType
    payload: Dict[str, Any]


@dataclass
class AgentResponse:
    """
    系統內部統一使用的回應格式。

    - ok: 是否成功
    - data: 成功時的資料 (任意結構，但建議用 dict/list)
    - error: 失敗時的人類可讀錯誤訊息
    """
    ok: bool
    data: Any | None = None
    error: Optional[str] = None


# ==== Agent 介面定義（Protocol） ==== #

@runtime_checkable
class ThemeAgentProtocol(Protocol):
    """ThemeAgent 必須實作的介面（之後在 agents/theme_agent.py 實作）"""

    def handle(self, payload: Dict[str, Any]) -> AgentResponse:
        """
        處理主題相關任務，例如：
        - 生成主題列表
        - 產生 Danbooru 風格的 prompt tags
        """
        ...


@runtime_checkable
class PostWriterAgentProtocol(Protocol):
    """PostWriterAgent 必須實作的介面（之後在 agents/post_writer_agent.py 實作）"""

    def handle(self, payload: Dict[str, Any]) -> AgentResponse:
        """
        處理貼文相關任務：
        - 根據作品 meta 生成日文/中文 caption
        - 依平台（X / Patreon / Pixiv）調整語氣與長度
        """
        ...


# ==== Orchestrator ==== #

class Orchestrator:
    """
    負責：
    - 根據 request.type 把任務丟到對應的 Agent
    - 做最基本的錯誤處理
    - 對外提供統一的 handle(request) 介面
    """

    def __init__(
        self,
        theme_agent: ThemeAgentProtocol,
        post_writer_agent: PostWriterAgentProtocol,
    ) -> None:
        self._theme_agent = theme_agent
        self._post_writer_agent = post_writer_agent

    def handle(self, request: AgentRequest) -> AgentResponse:
        """
        系統統一入口。

        之後：Telegram bot / Web API / CLI 都只需要建好 AgentRequest，丟進來就行。
        """
        try:
            if request.type == "generate_theme":
                return self._theme_agent.handle(request.payload)

            if request.type == "write_post":
                return self._post_writer_agent.handle(request.payload)

            return AgentResponse(
                ok=False,
                data=None,
                error=f"Unknown request type: {request.type}",
            )

        except Exception as e:  # 可以之後換成更細緻的錯誤類型
            return AgentResponse(
                ok=False,
                data=None,
                error=f"Unhandled exception in Orchestrator: {e}",
            )


# ==== 公用 Request Builder（給 API / Bot / CLI 共用） ==== #

def build_theme_request(
    *,
    count: int = 3,
    season: Optional[str] = None,
    focus: Optional[str] = None,
    platform: Optional[str] = None,
    nsfw_level: str = "sfw",
) -> AgentRequest:
    """
    幫你快速組一個 ThemeAgent 用的 AgentRequest。
    之後在 CLI / Web handler 裡可以重用。
    """
    payload: Dict[str, Any] = {
        "count": count,
        "nsfw_level": nsfw_level,
    }

    if season:
        payload["season"] = season
    if focus:
        payload["focus"] = focus
    if platform:
        payload["platform"] = platform

    return AgentRequest(type="generate_theme", payload=payload)


def build_post_request(
    *,
    platform: str,
    languages: list[str],
    artwork_meta: Dict[str, Any],
) -> AgentRequest:
    """
    幫你快速組一個 PostWriterAgent 用的 AgentRequest。
    """
    payload: Dict[str, Any] = {
        "platform": platform,
        "languages": languages,
        "artwork_meta": artwork_meta,
    }
    return AgentRequest(type="write_post", payload=payload)
