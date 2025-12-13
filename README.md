# 🎨 AI Illustration Agent Framework  
_Modular Multi-Agent System for Theme Generation, Prompt Building, and Post Writing_

This project is a **modular and extensible AI agent framework** designed for:

- Automated **anime-style illustration theme generation**
- Structured **Danbooru-style prompt tag** creation
- Multi-language **caption/post generation** (JP / ZH / EN)
- Cleanly separated layers for long-term maintainability

It is designed for creators who want a reliable backend for illustration production  
(Stable Diffusion, ComfyUI, image pipelines, X/Twitter posting bots, etc.).

---

# ✨ Features

### 🧠 Multi-Agent Architecture
- **ThemeAgent**  
  Produces illustration ideas (title, concept) and structured prompt tags.  
  Supports both rule-based logic and pluggable LLM-based generation.

- **PostWriterAgent**  
  Generates multilingual captions for platforms such as X/Twitter, Pixiv, Patreon.  
  Fully template-driven and highly customizable.

---

### 🔧 Skills Layer (Pluggable Modules)
Skills are isolated utilities that can be replaced or expanded without modifying agents.

- `PromptTemplateLibrary` — reusable Danbooru-tag structures  
- `CaptionTemplateLibrary` — caption templates per platform/language  
- `UserPreferenceStore` — personalization, favorite motifs, NSFW policy  
- `TrendFetcher` — seasonal/trending tag source  
- `ModelRunner` — interface for external or local LLMs  

Every component can be swapped independently via dependency injection.

---

### 📦 Storage Layer (Clean Architecture)
Data models use `dataclasses`:

- **ThemeRecord**
- **ArtworkRecord**
- **PostRecord**

Repositories implement a clean CRUD interface and can be easily adapted to:

- SQLite  
- PostgreSQL  
- JSON storage  
- Redis  
- Any ORM

---

# 📁 Project Structure

project_root/
│
├── app/
│ ├── orchestrator.py # Unified request router
│ └── main.py # Application entrypoint (no demo logic)
│
├── agents/
│ ├── theme_agent.py # Theme & prompt generation
│ └── post_writer_agent.py # Multilingual post writer
│
├── skills/
│ ├── prompt_templates.py # Danbooru tag templates
│ ├── caption_templates.py # Caption templates
│ ├── user_preferences.py # User preferences
│ ├── trend_fetcher.py # Seasonal / trending tags
│ └── model_runner.py # Interface for LLM integration
│
├── storage/
│ ├── model.py # Data models
│ └── repositories.py # Storage abstraction layer
│
└── (Optional: tests/, docs/, integration/)



---

# 🧠 Architecture Overview

## 🔸 1. Application Layer (`app/`)
Provides the **Orchestrator**, the unified interface used by external clients:

- Telegram bot  
- Web API  
- Cron job  
- Local scripts  
- Pipeline integration (ComfyUI, SDXL, LoRA trainer)

The Orchestrator routes tasks to the correct Agent based on request type.

---

## 🔸 2. Agents Layer (`agents/`)
Two core agents:

### **ThemeAgent**
- Generates illustration theme metadata  
- Uses PromptTemplates + UserPreferences + TrendFetcher  
- Optional: calls LLM via ModelRunner  
- Output includes:
  - title
  - short concept
  - structured prompt tags
  - nsfw level
  - metadata

---

### **PostWriterAgent**
- Generates multilingual captions  
- Supports platform-specific styles (X, Pixiv, Patreon)  
- Uses:
  - CaptionTemplates
  - User style preferences
  - Optional hashtag generator

Output includes a dict of posts per language.

---

## 🔸 3. Skills Layer (`skills/`)
Self-contained modules used by agents:

| Skill | Purpose |
|-------|---------|
| PromptTemplateLibrary | Base Danbooru-tag templates |
| CaptionTemplateLibrary | Platform/language caption templates |
| UserPreferenceStore | Favorite motifs, NSFW policy, tone defaults |
| TrendFetcher | Seasonal/trending tags |
| ModelRunner | External LLM interface |

Skills are small, pure, easy to replace.

---

## 🔸 4. Storage Layer (`storage/`)
### **Models**
All persistent items are Dataclasses:

- ThemeRecord  
- ArtworkRecord  
- PostRecord  

### **Repositories**
CRUD-based, backend-agnostic storage layer:

- ThemeRepository  
- ArtworkRepository  
- PostRepository  

These can be swapped into a SQL/NoSQL backend without changing agents.

---

# 🧩 Extending the System

## Add a new theme template
Edit:

skills/prompt_templates.py


## Adjust caption style
Edit:

skills/caption_templates.py
skills/user_preferences.py


## Add a new platform (Instagram, Weibo)
Extend:

CaptionTemplateLibrary
PostStylePreferenceStore


## Replace LLM with a real model
Implement:

class LLMModelRunner


and inject it into ThemeAgent.

## Switch storage to SQLite/Postgres
Replace Repository methods with DB queries.

---

# 📝 Design Principles

- **Layered architecture**  
  Each layer is isolated and interchangeable.

- **Dependency injection**  
  Agents never instantiate Skills internally.

- **No hidden state**  
  All operations are pure and predictable.

- **Schema-first data modeling**  
  All outputs follow a strict dataclass model.

- **Long-term maintainability**  
  New features can be added as new agents/modules.

---

# 📄 License

MIT License © 2025  
Feel free to use and modify for personal or commercial projects.