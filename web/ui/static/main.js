async function callApi(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API error (${res.status}): ${detail}`);
  }
  return await res.json();
}

function getLLMConfig() {
  const provider = document.getElementById("llm-provider").value || null;
  const modelInput = document.getElementById("llm-model").value || null;
  const baseUrl = document.getElementById("llm-base-url").value || null;

  const select = document.getElementById("llm-model-select");
  const selectedPath = select ? select.value || null : null;
  const selectedLabel =
    select && select.selectedIndex > 0
      ? select.options[select.selectedIndex].textContent
      : null;

  if (!provider && !modelInput && !baseUrl && !selectedPath) {
    return null;
  }

  // llama_cpp: 使用下拉選的 GGUF 路徑
  if (provider === "llama_cpp") {
    return {
      provider: "llama_cpp",
      model: modelInput || selectedLabel || "local-gguf",
      base_url: null,
      model_path: selectedPath, // 後端 LLMModelRunner 會用這個
    };
  }

  // 其他 provider (api / vllm): 延續原本邏輯
  return {
    provider,
    model: modelInput,
    base_url: baseUrl,
  };
}


async function fetchLlamaModels() {
  const res = await fetch("/api/llm/models");
  if (!res.ok) {
    throw new Error("Failed to fetch LLM models");
  }
  return await res.json(); // { models: [...] }
}

async function loadLlamaModelsIntoSelect() {
  const wrapper = document.getElementById("llm-model-select-wrapper");
  const select = document.getElementById("llm-model-select");

  try {
    const data = await fetchLlamaModels();
    const models = data.models || [];

    // 清空
    select.innerHTML = "";
    if (!models.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "(No .gguf models found in /models)";
      select.appendChild(opt);
      return;
    }

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "(Select a model)";
    select.appendChild(placeholder);

    models.forEach((m) => {
      const opt = document.createElement("option");
      // opt.value = full relative path, e.g. "models/Llama-3.2-8B-Q4_K_M.gguf"
      opt.value = m.path;
      opt.textContent = m.filename; // or m.id
      select.appendChild(opt);
    });
  } catch (err) {
    console.error(err);
    select.innerHTML = "";
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "(Error loading models)";
    select.appendChild(opt);
  }
}

function setupLLMProviderSwitch() {
  const providerEl = document.getElementById("llm-provider");
  const wrapper = document.getElementById("llm-model-select-wrapper");

  async function onChange() {
    const provider = providerEl.value;
    if (provider === "llama_cpp") {
      wrapper.style.display = "";
      await loadLlamaModelsIntoSelect();
    } else {
      wrapper.style.display = "none";
    }
  }

  providerEl.addEventListener("change", () => {
    onChange();
  });

  // 初始化時跑一次
  onChange();
}


function initThemeForm() {
  const form = document.getElementById("theme-form");
  const listEl = document.getElementById("theme-list");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    listEl.innerHTML = '<div class="loading">生成中...</div>';

    const season = document.getElementById("season").value || null;
    const focus = document.getElementById("focus").value || null;
    const platform = document.getElementById("platform").value || "x";
    const count = parseInt(document.getElementById("count").value || "3", 10);
    const llmConfig = getLLMConfig();
    const payload = {
      season,
      focus,
      platform,
      count,
      llm: llmConfig,
    };

    try {
      const data = await callApi("/api/themes/generate", payload);
      const themes = data.themes || [];

      if (!themes.length) {
        listEl.innerHTML = '<p class="empty">沒有生成任何主題。</p>';
        return;
      }

      listEl.innerHTML = "";
      themes.forEach((t, idx) => {
        const card = document.createElement("div");
        card.className = "card";

        const title = document.createElement("h4");
        title.textContent = `${idx + 1}. ${t.title}`;

        const concept = document.createElement("p");
        concept.className = "small";
        concept.textContent = t.short_concept;

        const tagsPre = document.createElement("pre");
        tagsPre.className = "tags-pre";
        tagsPre.textContent = JSON.stringify(t.prompt_tags, null, 2);

        card.appendChild(title);
        card.appendChild(concept);
        card.appendChild(tagsPre);

        listEl.appendChild(card);
      });
    } catch (err) {
      console.error(err);
      listEl.innerHTML = `<p class="error">Error: ${err.message}</p>`;
    }
  });
}

function initPostForm() {
  const form = document.getElementById("post-form");
  const listEl = document.getElementById("post-list");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    listEl.innerHTML = '<div class="loading">生成中...</div>';

    const platform = document.getElementById("post-platform").value || "x";

    const langCheckboxes = document.querySelectorAll(
      '#post-form input[name="languages"]:checked'
    );
    const languages = Array.from(langCheckboxes).map((cb) => cb.value);
    if (!languages.length) {
      listEl.innerHTML =
        '<p class="error">請至少選擇一種語言。</p>';
      return;
    }

    const title = document.getElementById("art-title").value || "Untitled";
    const mood = document.getElementById("art-mood").value || "";
    const tagsRaw = document.getElementById("art-tags").value || "";
    const charsRaw = document.getElementById("art-characters").value || "";
    const note = document.getElementById("art-note").value || "";
    const tone = document.getElementById("tone").value || "";

    const themeTags = tagsRaw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const characters = charsRaw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const style = tone ? { tone } : undefined;

    const payload = {
      platform,
      languages,
      artwork_meta: {
        title,
        mood,
        theme_tags: themeTags,
        characters,
        special_note: note,
      },
      style,
    };

    try {
      const data = await callApi("/api/posts/generate", payload);
      const posts = data.posts || {};

      const keys = Object.keys(posts);
      if (!keys.length) {
        listEl.innerHTML = '<p class="empty">沒有生成任何貼文。</p>';
        return;
      }

      listEl.innerHTML = "";
      keys.forEach((lang) => {
        const card = document.createElement("div");
        card.className = "card";

        const titleEl = document.createElement("h4");
        titleEl.textContent = `Language: ${lang}`;

        const textEl = document.createElement("pre");
        textEl.textContent = posts[lang];

        card.appendChild(titleEl);
        card.appendChild(textEl);
        listEl.appendChild(card);
      });
    } catch (err) {
      console.error(err);
      listEl.innerHTML = `<p class="error">Error: ${err.message}</p>`;
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupLLMProviderSwitch();  
  initThemeForm();
  initPostForm();
});
