from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Protocol, Optional, TYPE_CHECKING
from openai import OpenAI

try:
    # 需要: pip install openai
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    # 第三個 provider: llama.cpp (本地 GGUF)
    from llama_cpp import Llama
except ImportError:
    Llama = None

class ModelRunnerProtocol(Protocol):
    """
    ThemeAgent 用的 LLM 介面。

    任何想給 ThemeAgent 用的模型，都要實作這個 Protocol：
    - 可以是雲端 OpenAI
    - 也可以是本地 vLLM（OpenAI 相容 API）
    - 也可以是你自寫的其它 pipeline
    """

    def generate_themes(
        self,
        instruction: str,
        context: Dict[str, Any],
        count: int,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        回傳的 List 形式：

        [
          {
            "title": str,
            "short_concept": str,
            "keywords": [str, ...],
            "mood": [str, ...],
          },
          ...
        ]
        """
        ...


class LLMModelRunner(ModelRunnerProtocol):
    """
    通用 LLM ModelRunner，支援三種 provider：

    - "api"      : 雲端 OpenAI / 相容服務（chat.completions）
    - "vllm"     : 本地 vLLM server（OpenAI 相容 chat.completions）
    - "llama_cpp": 本地 GGUF 模型（llama-cpp-python, text completion）
    """

    def __init__(
        self,
        default_provider: str = "api",
        default_model: str = "gpt-4.1-mini",
        default_base_url: Optional[str] = None,
        temperature: float = 0.6,
        max_tokens: int = 800,
        default_api_key: Optional[str] = None,
    ) -> None:
        self._default_provider = default_provider
        self._default_model = default_model
        self._default_base_url = default_base_url
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._default_api_key = default_api_key

        # 專門給 llama.cpp 用的 cache，避免每次呼叫重載模型
        # use a string forward reference so the Llama name is not evaluated at runtime
        self._llama: Optional["Llama"] = None
        self._llama_model_path: Optional[str] = None


    # ========= 對 ThemeAgent 提供的介面 ========= #

    def generate_themes(
        self,
        instruction: str,
        context: Dict[str, Any],
        count: int,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        cfg = llm_config or {}
        provider = (cfg.get("provider") or self._default_provider).lower()
        model = cfg.get("model") or self._default_model
        base_url = cfg.get("base_url") or self._default_base_url
        api_key = cfg.get("api_key") or self._default_api_key

        # 1) 取得原始 LLM 輸出（字串）
        if provider in ("api", "vllm"):
            content = self._call_openai_like(
                provider=provider,
                model=model,
                base_url=base_url,
                api_key=api_key,
                instruction=instruction,
                context=context,
                count=count,
            )
        elif provider == "llama_cpp":
            content = self._call_llama_cpp(
                cfg=cfg,
                instruction=instruction,
                context=context,
                count=count,
            )
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

        # 2) 後處理：strip 圍欄、JSON parse、正規化結構
        content_stripped = self._strip_code_fences(content)

        try:
            data = json.loads(content_stripped)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to parse LLM JSON output: {e}\nRaw: {content}"
            ) from e

        if not isinstance(data, list):
            raise RuntimeError(f"Expected a list of themes, got: {type(data)}")

        normalized: List[Dict[str, Any]] = []
        for item in data[: max(count, 1)]:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "title": str(item.get("title", "Untitled Theme")),
                    "short_concept": str(item.get("short_concept", "")),
                    "keywords": self._ensure_str_list(item.get("keywords", [])),
                    "mood": self._ensure_str_list(item.get("mood", [])),
                }
            )

        if not normalized:
            raise RuntimeError(f"LLM returned empty or invalid theme list. Raw: {content}")

        return normalized

    # ========= OpenAI / vLLM 共用邏輯 ========= #

    def _call_openai_like(
        self,
        provider: str,
        model: str,
        base_url: Optional[str],
        api_key: Optional[str],
        instruction: str,
        context: Dict[str, Any],
        count: int,
    ) -> str:
        if provider == "api":
            if api_key is None:
                raise RuntimeError(
                    "LLM provider 'api' requires api_key. "
                    "You can set it via llm_config['api_key'] or default_api_key."
                )
            client = OpenAI(api_key=api_key, base_url=base_url)
        elif provider == "vllm":
            if base_url is None:
                raise RuntimeError(
                    "LLM provider 'vllm' requires base_url (e.g. http://localhost:8000/v1)"
                )
            client = OpenAI(api_key=api_key or "DUMMY_KEY", base_url=base_url)
        else:
            raise ValueError(f"Unexpected provider for _call_openai_like: {provider}")

        messages = self._build_messages(instruction, context, count)

        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )

        return resp.choices[0].message.content or ""

    # ========= llama.cpp (本地 GGUF) ========= #

    def _call_llama_cpp(
        self,
        cfg: Dict[str, Any],
        instruction: str,
        context: Dict[str, Any],
        count: int,
    ) -> str:
        if Llama is None:
            raise RuntimeError(
                "llama-cpp-python is not installed. "
                "Please run: pip install llama-cpp-python"
            )

        # 模型路徑:
        #   1) llm_config["model_path"]
        #   2) 環境變數 LLAMA_CPP_MODEL_PATH
        model_path = cfg.get("model_path") or os.getenv("LLAMA_CPP_MODEL_PATH")
        if not model_path:
            raise RuntimeError(
                "LLM provider 'llama_cpp' requires a model_path.\n"
                "Set it via llm_config['model_path'] or env LLAMA_CPP_MODEL_PATH."
            )

        n_ctx = int(cfg.get("n_ctx") or os.getenv("LLAMA_CPP_N_CTX") or 4096)
        n_gpu_layers = int(
            cfg.get("n_gpu_layers") or os.getenv("LLAMA_CPP_N_GPU_LAYERS") or -1
        )

        # Lazy load + cache，同一個 model_path 只載一次
        if self._llama is None or self._llama_model_path != model_path:
            self._llama = Llama(
                model_path=model_path,
                n_ctx=n_ctx,
                n_gpu_layers=n_gpu_layers,
                embedding=False,
            )
            self._llama_model_path = model_path

        prompt = self._build_llama_prompt(instruction, context, count)

        # llama-cpp-python 預設是 text completion 風格
        output = self._llama(
            prompt,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            stop=["```", "</json>"],
        )

        # 不同版本的 llama-cpp-python 可能 key 名稱略有差異
        if isinstance(output, dict):
            # 新版: output["choices"][0]["text"]
            choices = output.get("choices") or []
            if choices and "text" in choices[0]:
                return choices[0]["text"] or ""
            # 舊版: 可能是 output["choices"][0]["message"]["content"]
            if choices and "message" in choices[0]:
                return choices[0]["message"].get("content", "") or ""

        # fallback：直接轉字串
        return str(output)

    # ========= 內部工具 ========= #

    def _build_messages(
        self,
        instruction: str,
        context: Dict[str, Any],
        count: int,
    ) -> List[Dict[str, Any]]:
        """
        組成給 chat.completions 用的 messages。
        強制要求 LLM 回傳「純 JSON array」，方便 parse。
        """
        options = context.get("options") or {}
        trend_tags = context.get("trend_tags") or []
        preferences = context.get("preferences") or {}

        system_prompt = """
You are a theme generator for 2D anime-style illustrations.

Return ONLY a valid JSON array. Do not include any extra text.
Each element in the array must be an object with the following fields:
- "title": string
- "short_concept": string
- "keywords": array of short English-like tags
- "mood": array of mood words (e.g. "soft", "bright", "nostalgic")

Example output:
[
  {
    "title": "Summer Beach Evening",
    "short_concept": "A girl in a frilled bikini at sunset by the sea.",
    "keywords": ["frilled_bikini", "beach", "sunset"],
    "mood": ["warm", "relaxed"]
  }
]
        """.strip()

        user_prompt = {
            "instruction": instruction,
            "count": count,
            "options": options,
            "trend_tags": trend_tags,
            "preferences": preferences,
        }

        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(user_prompt, ensure_ascii=False),
            },
        ]

    def _build_llama_prompt(
        self,
        instruction: str,
        context: Dict[str, Any],
        count: int,
    ) -> str:
        """
        給 llama.cpp 的 text prompt。
        直接把 system 說明 + user JSON 串成一段文字。
        """
        options = context.get("options") or {}
        trend_tags = context.get("trend_tags") or []
        preferences = context.get("preferences") or {}

        user_payload = {
            "instruction": instruction,
            "count": count,
            "options": options,
            "trend_tags": trend_tags,
            "preferences": preferences,
        }

        system_prompt = """
You are a theme generator for 2D anime-style illustrations.

Return ONLY a valid JSON array. Do not include any extra text.
Each element in the array must be an object with the following fields:
- "title": string
- "short_concept": string
- "keywords": array of short English-like tags
- "mood": array of mood words (e.g. "soft", "bright", "nostalgic")
        """.strip()

        prompt = (
            system_prompt
            + "\n\nUser JSON:\n"
            + json.dumps(user_payload, ensure_ascii=False)
            + "\n\nOutput JSON array only:"
        )
        return prompt

    # ========= 小工具 ========= #

    def _strip_code_fences(self, text: str) -> str:
        """
        把 ```json ... ``` 或 ``` ... ``` 外層拿掉。
        """
        stripped = text.strip()
        if stripped.startswith("```"):
            # 可能是 ```json\n...\n```
            stripped = stripped.strip("`")
            # 如果還帶有語言標記 json / JSON
            parts = stripped.split("\n", 1)
            if len(parts) == 2 and parts[0].lower().startswith("json"):
                stripped = parts[1]
        return stripped.strip()

    def _ensure_str_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(v) for v in value]
        if isinstance(value, str):
            return [value]
        return [str(value)]


__all__ = ["ModelRunnerProtocol", "LLMModelRunner"]
