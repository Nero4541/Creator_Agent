import re
from typing import List

class TipoTagger:
    """
    負責處理 TIPO 模型的 Prompt 建構與輸出解析。
    """

    # TIPO 建議排除的 Tag (避免汙染畫面或生成無意義標籤)
    # 參考官方實作的 Ban List
    BAN_TAGS = {
        "background", "name", "text", "joke", "costume", 
        "alternative", "speech", "stickers", "hat",
        "signature", "watermark", "username", "artist name"
    }

    # TIPO 的特殊格式 token，解析輸出時需要移除
    SPECIAL_TOKENS = [
        "<|special|>", "<|characters|>", "<|copyrights|>", 
        "<|artist|>", "<|general|>", "<|generated|>", 
        "<|quality|>", "<|meta|>", "<|rating|>", "<|extended|>"
    ]

    def build_prompt(self, nl_prompt: str, current_tags: List[str] = None) -> str:
        """
        建構給 TIPO 模型 (Completion Mode) 用的 Prompt。
        TIPO 最佳實務格式： Natural Language -> <|extended|> -> Tags
        """
        # 1. 清理自然語言輸入 (移除多餘換行，避免模型誤判停止)
        clean_nl = nl_prompt.replace("\n", " ").strip()
        
        # 2. 建構核心 Prompt
        # <|extended|> 是告訴 TIPO "我要開始擴充標籤了" 的關鍵 token
        prompt = f"{clean_nl}\n<|extended|>\n"
        
        # 3. 如果已經有部分 Tags (例如從 Main LLM 來的)，加在後面作為引導
        if current_tags:
            valid_tags = [t.strip().lower() for t in current_tags if t.strip()]
            if valid_tags:
                prompt += ", ".join(valid_tags) + ","

        return prompt

    def parse_output(self, raw_output: str) -> List[str]:
        """
        解析模型的原始輸出，移除特殊標記並清洗格式。
        """
        text = raw_output
        
        # 1. 移除所有特殊控制 token
        for token in self.SPECIAL_TOKENS:
            text = text.replace(token, "")
            
        # 2. 處理轉義字元 (TIPO 有時會輸出 \(tag\))
        text = re.sub(r"\\([()\[\]])", r"\1", text)
        
        # 3. 轉成 List
        tags = [t.strip().lower() for t in text.split(",") if t.strip()]
        
        # 4. 過濾 Ban Tags
        final_tags = [t for t in tags if t not in self.BAN_TAGS]
        
        # 5. 去重 (保持順序)
        seen = set()
        deduped = []
        for t in final_tags:
            if t not in seen:
                seen.add(t)
                deduped.append(t)
                
        return deduped