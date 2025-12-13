from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import AgentRequest, RequestType, AgentResponse
from .deps import get_orchestrator
from .schemas import (
    GenerateThemeRequest,
    GenerateThemeResponse,
    GeneratePostRequest,
    GeneratePostResponse,
    LLMModelListResponse,
    LLMModelInfo,
)

app = FastAPI(title="MCP Agent Web API")

# ==== Frontend (WebUI) settings ====

ROOT = Path(__file__).resolve().parents[2]     # MCP_Agent/
UI_DIR = ROOT / "web" / "ui"
STATIC_DIR = UI_DIR / "static"

MODEL_DIR = ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)  # 如果沒這個資料夾就自動建立


# 掛載 /static，如果資料夾不存在也不要讓整個 app 掛掉
if STATIC_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=STATIC_DIR),
        name="static",
    )


@app.get("/", response_class=HTMLResponse)
def index_page():
    """
    Root: serve WebUI if index.html exists,
    otherwise show a minimal placeholder page.
    """
    index_path = UI_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")

    # fallback：至少顯示一個簡單頁面，避免 500
    return HTMLResponse(
        content="""
<!DOCTYPE html>
<html>
  <head><meta charset="utf-8"><title>MCP Agent</title></head>
  <body style="background:#020617;color:#e5e7eb;font-family:sans-serif;padding:16px;">
    <h1>MCP Agent API</h1>
    <p>Web UI index.html not found.</p>
    <p>Please create: <code>web/ui/index.html</code></p>
    <p>API health check: <a href="/api/health">/api/health</a></p>
  </body>
</html>
        """,
        status_code=200,
    )

@app.get("/api/llm/models", response_model=LLMModelListResponse)
def list_llm_models():
    """
    列出 MCP_Agent/models/ 底下所有 .gguf 模型，給 WebUI 下拉選單用。
    """
    models: list[LLMModelInfo] = []

    if MODEL_DIR.exists():
        for p in MODEL_DIR.glob("*.gguf"):
            models.append(
                LLMModelInfo(
                    id=p.stem,
                    filename=p.name,
                    path=str(p.relative_to(ROOT)),  # e.g. "models/xxx.gguf"
                )
            )

    # 可以按照名稱排序一下
    models.sort(key=lambda m: m.filename.lower())

    return LLMModelListResponse(models=models)

# ==== API routes ====

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/themes/generate", response_model=GenerateThemeResponse)
def generate_themes(
    body: GenerateThemeRequest,
    orchestrator=Depends(get_orchestrator),
):
    req = AgentRequest(
        type="generate_theme",
        payload=body.model_dump(),
    )
    res: AgentResponse = orchestrator.handle(req)
    if not res.ok:
        raise HTTPException(status_code=500, detail=res.error or "ThemeAgent error")

    return GenerateThemeResponse(**res.data)


@app.post("/api/posts/generate", response_model=GeneratePostResponse)
def generate_posts(
    body: GeneratePostRequest,
    orchestrator=Depends(get_orchestrator),
):
    req = AgentRequest(
        type="write_post",
        payload=body.model_dump(),
    )
    res: AgentResponse = orchestrator.handle(req)
    if not res.ok:
        raise HTTPException(status_code=500, detail=res.error or "PostWriterAgent error")

    return GeneratePostResponse(**res.data)
