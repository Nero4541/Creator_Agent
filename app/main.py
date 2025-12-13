from __future__ import annotations

from agents import ThemeAgent, PostWriterAgent

from skills import (
    SimplePromptTemplateLibrary,
    SimpleCaptionTemplateLibrary,
    SimpleUserPreferenceStore,
    SimplePostStylePreferenceStore,
    SimpleTrendFetcher,
    LLMModelRunner,
)
from .orchestrator import Orchestrator


def create_app() -> Orchestrator:
    """
    建立整個應用的 Orchestrator 實例。

    這裡只做「正式依賴注入」：
    - 初始化各種 Skills（templates / preferences / trend_fetcher / model_runner）
    - 建立 ThemeAgent / PostWriterAgent
    - 回傳 Orchestrator

    外部（例如 API / bot / CLI）只需要呼叫 create_app() 拿到 orchestrator，
    再用 orchestrator.handle(request) 來執行任務。
    """

    # === Skills 層 === #
    prompt_templates = SimplePromptTemplateLibrary()
    user_prefs = SimpleUserPreferenceStore()
    trend_fetcher = SimpleTrendFetcher()
    model_runner = LLMModelRunner()  

    caption_templates = SimpleCaptionTemplateLibrary()
    style_prefs = SimplePostStylePreferenceStore()


    # === Agents 層 === #
    theme_agent = ThemeAgent(
        prompt_templates=prompt_templates,
        user_prefs=user_prefs,
        trend_fetcher=trend_fetcher,
        model_runner=model_runner,
    )

    post_agent = PostWriterAgent(
        caption_templates=caption_templates,
        style_prefs=style_prefs,
        hashtag_generator=None,  # 之後可接 HashtagGenerator 實作
    )

    # === Orchestrator === #
    return Orchestrator(theme_agent=theme_agent, post_writer_agent=post_agent)
