from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel

class LLMConfig(BaseModel):
    provider: Optional[str] = None 
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None   # 通常不會從 UI 傳，但先保留欄位
    model_path: Optional[str] = None

class LLMModelInfo(BaseModel):
    id: str          # 用於 dropdown 顯示，例如 "Llama-3.2-8B-Q4_K_M"
    filename: str    # 檔名，例如 "Llama-3.2-8B-Q4_K_M.gguf"
    path: str        # 後端用的相對路徑，例如 "models/Llama-3.2-8B-Q4_K_M.gguf"


class LLMModelListResponse(BaseModel):
    models: List[LLMModelInfo]

class GenerateThemeRequest(BaseModel):
    season: Optional[str] = None
    focus: Optional[str] = None
    platform: Optional[str] = "x"
    count: int = 3
    llm: Optional[LLMConfig] = None

class ThemeItem(BaseModel):
    title: str
    short_concept: str
    keywords: List[str]
    mood: List[str]
    prompt_tags: Dict[str, List[str]]
    nsfw_level: str
    meta: Dict[str, Any]


class GenerateThemeResponse(BaseModel):
    themes: List[ThemeItem]


class CaptionStylePayload(BaseModel):
    tone: Optional[str] = None


class GeneratePostRequest(BaseModel):
    platform: str
    languages: List[str]
    artwork_meta: Dict[str, Any]
    style: Optional[CaptionStylePayload] = None


class GeneratePostResponse(BaseModel):
    posts: Dict[str, str]

__all__ = [
    "GenerateThemeRequest",
    "GenerateThemeResponse",
    "GeneratePostRequest",
    "GeneratePostResponse",
    "LLMModelInfo",
    "LLMModelListResponse",
]
