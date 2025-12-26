from __future__ import annotations

import json
import os
import re
import gc
from typing import Any, Dict, List, Protocol, Optional, TYPE_CHECKING
from skills.tipo_tagger import TipoTagger

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

class ModelRunnerProtocol(Protocol):
    def generate_themes(
        self,
        instruction: str,
        context: Dict[str, Any],
        count: int,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        ...

class LLMModelRunner(ModelRunnerProtocol):
    def __init__(
        self,
        default_provider: str = "api",
        default_model: str = "gpt-4.1-mini",
        default_base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096, 
        default_api_key: Optional[str] = None,
    ) -> None:
        self._default_provider = default_provider
        self._default_model = default_model
        self._default_base_url = default_base_url
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._default_api_key = default_api_key

        # Llama.cpp 相關狀態
        self._llama: Any = None
        self._llama_model_path: Optional[str] = None
        self._llama_use_gpu: Optional[bool] = None

        # TIPO 輔助工具
        self._tipo_helper = TipoTagger()

    def unload_model(self) -> None:
        if self._llama is not None:
            print("[LLMModelRunner] Unloading llama.cpp model...")
            del self._llama
            self._llama = None
            self._llama_model_path = None
            self._llama_use_gpu = None
            gc.collect()

    def generate_themes(
        self,
        instruction: str,
        context: Dict[str, Any],
        count: int,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        
        cfg = llm_config or {}
        provider = (cfg.get("provider") or self._default_provider).lower()
        # 取得 TIPO 模型路徑
        tipo_path = cfg.get("tipo_model_path")
        
        try:
            # === STEP 1: 自然語言創意發想 (Ideation) ===
            print(f"[ModelRunner] Step 1: Generating natural language ideas ({count} items)...")
            
            ideation_prompt = self._build_ideation_prompt(instruction, context, count)
            raw_text = self._execute_inference(provider, cfg, ideation_prompt)
            
            # === STEP 2: 格式轉換 (Extraction to JSON) ===
            print(f"[ModelRunner] Step 2: Converting to JSON...")
            
            extraction_prompt = self._build_extraction_prompt(raw_text, count)
            extraction_cfg = cfg.copy()
            
            json_text = self._execute_inference(provider, extraction_cfg, extraction_prompt)
            
            # 解析 JSON
            themes = self._parse_json_result(json_text, count)

            # === STEP 3: TIPO Tagging (Enhancement) ===
            if tipo_path and os.path.exists(tipo_path):
                print(f"[ModelRunner] Step 3: Enhancing tags with TIPO...")
                
                # 如果主模型是本地的 llama.cpp，先卸載以騰出 VRAM 給 TIPO
                if provider == "llama_cpp":
                    self.unload_model()

                # 設定 TIPO 參數
                tipo_cfg = cfg.copy()
                tipo_cfg["model_path"] = tipo_path
                tipo_cfg["n_ctx"] = 1024 # TIPO 不需要太長的 context
                
                for theme in themes:
                    concept = theme.get("short_concept", "")
                    
                    if concept:
                        # 將目前的 keywords 作為 base_tags 傳入
                        base_tags = ", ".join(theme.get("keywords", []))
                        
                        # 呼叫 TIPO 進行擴充/轉換
                        generated_tags = self._call_tipo(tipo_cfg, concept, base_tags)
                        
                        # 更新 keywords
                        if generated_tags:
                            new_tags = [t.strip() for t in generated_tags.split(",") if t.strip()]
                            theme["keywords"] = new_tags
                            print(f"  -> TIPO processed: {theme['title']}")

            return themes

        finally:
            if cfg.get("unload_after_generate", False) and provider == "llama_cpp":
                self.unload_model()

    # ========= 核心執行邏輯 (封裝) ========= #

    def _execute_inference(self, provider: str, cfg: Dict[str, Any], prompt_messages: Any) -> str:
        """
        統一執行推論 (主要用於 Step 1 & 2)
        """
        model = cfg.get("model") or self._default_model
        base_url = cfg.get("base_url") or self._default_base_url
        api_key = cfg.get("api_key") or self._default_api_key

        if provider in ("api", "vllm"):
            return self._call_openai_like(provider, model, base_url, api_key, prompt_messages)
        elif provider == "llama_cpp":
            text_prompt = prompt_messages
            if isinstance(prompt_messages, list):
                text_prompt = "\n\n".join([m["content"] for m in prompt_messages])
                text_prompt += "\n\nResponse:"

            return self._call_llama_cpp(cfg, text_prompt)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    # ========= TIPO 專用呼叫邏輯 ========= #

    def _call_tipo(self, cfg: Dict[str, Any], nl_prompt: str, base_tags: str = "") -> str:
        """
        執行 TIPO-500M 生成 (Text Completion)。
        """
        if Llama is None:
            print("[ModelRunner] llama-cpp-python not installed, skipping TIPO.")
            return base_tags

        # 1. 準備 Prompt (使用 TipoTagger Helper)
        base_tags_list = [t.strip() for t in base_tags.split(",") if t.strip()]
        input_prompt = self._tipo_helper.build_prompt(nl_prompt, base_tags_list)

        model_path = cfg.get("model_path")
        use_gpu = cfg.get("use_gpu", True)
        
        # 2. 載入模型 (如果尚未載入或是不同的模型)
        if (self._llama is None or 
            self._llama_model_path != model_path or 
            self._llama_use_gpu != use_gpu):
            
            self.unload_model()
            # print(f"[LLM] Loading TIPO: {os.path.basename(model_path)} (GPU={use_gpu})")
            
            n_gpu_layers = int(cfg.get("n_gpu_layers") or (-1 if use_gpu else 0))
            n_ctx = int(cfg.get("n_ctx") or 1024)

            try:
                self._llama = Llama(
                    model_path=model_path,
                    n_ctx=n_ctx,
                    n_gpu_layers=n_gpu_layers,
                    embedding=False,
                    verbose=False
                )
                self._llama_model_path = model_path
                self._llama_use_gpu = use_gpu
            except Exception as e:
                print(f"[ModelRunner] Failed to load TIPO model: {e}")
                return base_tags

        # 3. 執行生成 (Text Completion)
        try:
            output = self._llama(
                prompt=input_prompt,
                max_tokens=256,
                temperature=0.5, # TIPO 推薦較低的 temperature
                top_p=0.95,
                stop=["<|quality|>", "<|meta|>", "<|rating|>", "\n\n"], # TIPO 專用停止詞
                echo=False
            )
            
            result_text = ""
            if isinstance(output, dict):
                choices = output.get("choices", [])
                if choices:
                    result_text = choices[0].get("text", "")
            else:
                result_text = str(output)

            # 4. 解析與合併結果 (使用 TipoTagger Helper)
            final_tags_list = self._tipo_helper.parse_output(result_text)
            
            # 合併原始 tags (base_tags) 與新生成的 tags
            # 使用 set 去重並保持順序
            seen = set()
            merged_list = []
            
            # 先加原本的
            for t in base_tags_list:
                t_lower = t.lower()
                if t_lower not in seen:
                    seen.add(t_lower)
                    merged_list.append(t_lower)
            
            # 再加生成的
            for t in final_tags_list:
                if t not in seen:
                    seen.add(t)
                    merged_list.append(t)
            
            return ", ".join(merged_list)

        except Exception as e:
            print(f"[ModelRunner] TIPO Inference Error: {e}")
            return base_tags

    # ========= Prompt 建構 (兩階段) ========= #

    def _build_ideation_prompt(self, instruction: str, context: Dict[str, Any], count: int):
        options = context.get("options") or {}
        trend_tags = context.get("trend_tags") or []
        
        system_content = (
            "You are a creative director for anime illustrations. "
            "Brainstorm creative concepts based on the user's request. "
            "Do not worry about JSON format yet. Just write natural descriptions."
        )
        
        user_content = f"""
Request: {instruction}
Target Count: {count}
Season: {options.get('season', 'Any')}
Focus: {options.get('focus', 'Any')}
Trending Tags to consider: {', '.join(trend_tags[:10])}

Please list {count} distinct theme ideas. For each theme, describe:
1. A catchy Title.
2. A Short Concept (1-2 sentences).
3. Visual Keywords (list of tags).
4. Atmosphere/Mood.

Output Format: Plain text list.
"""
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]

    def _build_extraction_prompt(self, raw_text: str, count: int):
        system_content = (
            "You are a strict data formatting assistant. "
            "Convert the provided text into a valid JSON array. "
            "Do not add any explanations. Output ONLY the JSON."
        )
        
        user_content = f"""
Source Text:
---
{raw_text}
---

Task: Extract {count} themes from the text above into a JSON array.
Each object must have these exact keys:
- "title": string
- "short_concept": string
- "keywords": array of strings
- "mood": array of strings
"""
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]

    # ========= OpenAI / Llama 一般呼叫 ========= #

    def _call_openai_like(self, provider, model, base_url, api_key, messages) -> str:
        if provider == "api":
            client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            client = OpenAI(api_key=api_key or "DUMMY", base_url=base_url)
            
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        return resp.choices[0].message.content or ""

    def _call_llama_cpp(self, cfg, prompt_text: str) -> str:
        if Llama is None:
            raise RuntimeError("llama-cpp-python not installed.")

        model_path = cfg.get("model_path") or os.getenv("LLAMA_CPP_MODEL_PATH")
        if not model_path:
            raise RuntimeError("No model_path provided for llama_cpp.")

        use_gpu = cfg.get("use_gpu", True)
        n_gpu_layers = int(cfg.get("n_gpu_layers") or (-1 if use_gpu else 0))
        n_ctx = int(cfg.get("n_ctx") or 4096)

        if (self._llama is None or 
            self._llama_model_path != model_path or 
            self._llama_use_gpu != use_gpu):
            
            self.unload_model()
            print(f"[LLM] Loading: {os.path.basename(model_path)} (GPU={use_gpu})")
            
            self._llama = Llama(
                model_path=model_path,
                n_ctx=n_ctx,
                n_gpu_layers=n_gpu_layers,
                embedding=False,
                verbose=False
            )
            self._llama_model_path = model_path
            self._llama_use_gpu = use_gpu

        output = self._llama(
            prompt_text,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            stop=["</json>", "User JSON:"],
            echo=False,
        )

        if isinstance(output, dict):
            choices = output.get("choices", [])
            if choices:
                return choices[0].get("text", "")
        return str(output)

    # ========= JSON 解析 ========= #

    def _parse_json_result(self, json_text: str, count: int) -> List[Dict[str, Any]]:
        cleaned = self._strip_code_fences(json_text)
        
        match = re.search(r'\[.*\]', cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)
            
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            if "Expecting value" in str(e) and not cleaned.endswith("]"):
                try:
                    fixed = cleaned.rsplit("}", 1)[0] + "}]"
                    data = json.loads(fixed)
                except:
                    raise RuntimeError(f"JSON Parse Failed: {e}\nContent: {json_text[:200]}...")
            else:
                 raise RuntimeError(f"JSON Parse Failed: {e}\nContent: {json_text[:200]}...")

        if not isinstance(data, list):
            if isinstance(data, dict) and "themes" in data:
                data = data["themes"]
            else:
                raise RuntimeError("Extracted JSON is not a list.")

        normalized = []
        for item in data[: max(count, 1)]:
            if not isinstance(item, dict): continue
            normalized.append({
                "title": str(item.get("title", "Untitled")),
                "short_concept": str(item.get("short_concept", "")),
                "keywords": self._ensure_str_list(item.get("keywords", [])),
                "mood": self._ensure_str_list(item.get("mood", [])),
            })
        return normalized

    def _strip_code_fences(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            parts = text.split("\n", 1)
            if len(parts) == 2:
                text = parts[1]
        return text.strip()

    def _ensure_str_list(self, value: Any) -> List[str]:
        if isinstance(value, list): return [str(v) for v in value]
        if isinstance(value, str): return [value]
        return [str(value)]

__all__ = ["ModelRunnerProtocol", "LLMModelRunner"]