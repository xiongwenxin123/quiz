const languageDefaults = {
  en: { label: "EN", system: "CEFR", levels: ["A1", "A2", "B1", "B2", "C1", "C2"], defaultLevel: "B1" },
  ja: { label: "JA", system: "JLPT", levels: ["N5", "N4", "N3", "N2", "N1"], defaultLevel: "N3" },
  es: { label: "ES", system: "CEFR", levels: ["A1", "A2", "B1", "B2", "C1", "C2"], defaultLevel: "B1" },
};

const questionTypes = [
  { id: "main_idea", label: "主旨理解", hint: "全文核心观点", count: 0 },
  { id: "detail", label: "细节定位", hint: "事实与信息关系", count: 2 },
  { id: "inference", label: "推断理解", hint: "文本强支持结论", count: 1 },
  { id: "author_purpose", label: "作者目的", hint: "结构、态度与作用", count: 0 },
  { id: "vocabulary_context", label: "语境词汇", hint: "当前语境中的意义", count: 2 },
  { id: "cloze", label: "语境完形", hint: "搭配与篇章衔接", count: 0 },
  { id: "grammar", label: "语法应用", hint: "形式、意义与功能", count: 1 },
  { id: "true_false", label: "判断题", hint: "快速验证陈述", count: 0 },
  { id: "short_answer", label: "简答题", hint: "主动提取与表达", count: 0 },
];

const typeLabels = Object.fromEntries(questionTypes.map((item) => [item.id, item.label]));
const sampleArticles = {
  en: "Many cities are planting trees to reduce summer heat. Trees shade streets and release water vapor, which can lower nearby temperatures. However, urban trees need careful planning because roots may damage sidewalks and young trees require regular watering. Researchers recommend choosing native species and planting them where residents receive the greatest benefit. A successful program therefore combines environmental goals with long-term maintenance.",
  ja: "近年、食品ロスを減らすために、売れ残った料理を安く提供する店が増えています。利用者はアプリで商品を予約し、閉店前に店で受け取ります。店にとっては廃棄費用を減らせるという利点があります。一方で、毎日同じ商品が残るとは限らないため、利用者は内容を自由に選べないこともあります。この仕組みを続けるには、便利さだけでなく、店と利用者の理解も必要です。",
  es: "Cada vez más barrios organizan mercados de intercambio para dar una segunda vida a los objetos. Los participantes llevan libros, ropa o utensilios que ya no usan y los cambian por otros productos. La iniciativa no solo reduce los residuos, sino que también permite conocer a los vecinos. Para que el evento funcione, los organizadores piden que todos los objetos estén limpios y en buen estado. Así, el intercambio se convierte en una actividad útil y agradable para toda la comunidad.",
};

const state = {
  sourceMode: "text",
  language: "en",
  counts: Object.fromEntries(questionTypes.map((item) => [item.id, item.count])),
  package: null,
  questionIndex: 0,
  answers: {},
  submitted: {},
  scores: {},
  loadingTimer: null,
  runtimeMode: "production",
  providerSettings: null,
  defaultProvider: null,
};

const providerPresets = {
  openai: "https://api.openai.com/v1",
  qwen: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  deepseek: "https://api.deepseek.com/v1",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderBlueprint() {
  $("#question-blueprint").innerHTML = questionTypes.map((item) => `
    <div class="blueprint-row">
      <div class="blueprint-label"><strong>${item.label}</strong><small>${item.hint}</small></div>
      <div class="stepper" data-question-type="${item.id}">
        <button type="button" data-delta="-1" aria-label="减少${item.label}" title="减少">−</button>
        <output>${state.counts[item.id]}</output>
        <button type="button" data-delta="1" aria-label="增加${item.label}" title="增加">+</button>
      </div>
    </div>`).join("");
  updateTotal();
}

function updateTotal() {
  $("#question-total").textContent = Object.values(state.counts).reduce((sum, value) => sum + value, 0);
}

function setLanguage(language) {
  state.language = language;
  $$(".language-option").forEach((button) => {
    const selected = button.dataset.language === language;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-checked", String(selected));
  });
  const config = languageDefaults[language];
  $("#level-label").textContent = `${config.system} 等级`;
  $("#level-select").innerHTML = config.levels.map((level) => `<option value="${level}"${level === config.defaultLevel ? " selected" : ""}>${level}</option>`).join("");
  $("#spanish-variant-field").hidden = language !== "es";
  $("#furigana-field").hidden = language !== "ja";
}

function setSourceMode(mode) {
  state.sourceMode = mode;
  $$('[data-source-mode]').forEach((button) => {
    const selected = button.dataset.sourceMode === mode;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", String(selected));
  });
  $("#text-source-panel").hidden = mode !== "text";
  $("#url-source-panel").hidden = mode !== "url";
  $("#source-text").required = mode === "text";
  $("#source-url").required = mode === "url";
}

function buildRequest() {
  const counts = questionTypes
    .filter((item) => state.counts[item.id] > 0)
    .map((item) => ({ type: item.id, count: state.counts[item.id] }));
  const request = {
    target_language: state.language,
    level: $("#level-select").value,
    explanation_language: $("#explanation-language").value,
    question_counts: counts,
    spanish_variant: $("#spanish-variant").value,
    include_furigana: $("#include-furigana").checked,
    max_repair_attempts: 1,
  };
  if (state.sourceMode === "text") request.source_text = $("#source-text").value.trim();
  else request.source_url = $("#source-url").value.trim();
  return request;
}

function validateRequest(request) {
  if (!request.question_counts.length) return "请至少选择一道题。";
  if (state.sourceMode === "text" && request.source_text.length < 80) return "文章正文至少需要 80 个字符。";
  if (state.sourceMode === "url" && !request.source_url) return "请输入公开文章 URL。";
  return "";
}

function setLoading(loading) {
  $("#generate-button").disabled = loading;
  $("#generate-button").classList.toggle("loading", loading);
  $("#empty-state").hidden = loading || Boolean(state.package);
  $("#loading-state").hidden = !loading;
  $("#quiz-view").hidden = loading || !state.package;
  clearInterval(state.loadingTimer);
  if (loading) {
    const messages = ["正在分析文章结构...", "正在选择词汇与语法目标...", "正在生成并校验题目...", "正在整理原文证据..."];
    let index = 0;
    $("#loading-message").textContent = messages[0];
    state.loadingTimer = setInterval(() => {
      index = (index + 1) % messages.length;
      $("#loading-message").textContent = messages[index];
    }, 2200);
  }
}

function parseError(body, status) {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join("；");
  return `生成失败（HTTP ${status}）`;
}

async function generateQuiz(event) {
  event.preventDefault();
  const request = buildRequest();
  const error = validateRequest(request);
  $("#form-error").hidden = !error;
  $("#form-error").textContent = error;
  if (error) return;

  state.package = null;
  setLoading(true);
  try {
    const headers = { "Content-Type": "application/json" };
    if (state.providerSettings) {
      headers["X-Quiz-LLM-API-Key"] = state.providerSettings.apiKey;
      headers["X-Quiz-LLM-Model"] = state.providerSettings.model;
      headers["X-Quiz-LLM-Base-URL"] = state.providerSettings.baseUrl;
      headers["X-Quiz-LLM-Compatibility"] = state.providerSettings.compatibilityMode;
      if (state.providerSettings.allowInsecureHttp) headers["X-Quiz-Allow-Insecure-HTTP"] = "true";
    }
    const response = await fetch("/v1/quizzes", {
      method: "POST",
      headers,
      body: JSON.stringify(request),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(parseError(body, response.status));
    state.package = body;
    state.questionIndex = 0;
    state.answers = {};
    state.submitted = {};
    state.scores = {};
    renderPackage();
  } catch (caught) {
    $("#form-error").textContent = caught.message || "生成失败，请检查服务配置。";
    $("#form-error").hidden = false;
    showToast("练习生成失败");
  } finally {
    setLoading(false);
  }
}

function renderPackage() {
  const data = state.package;
  const language = languageDefaults[data.metadata.target_language] || languageDefaults.en;
  $("#result-kicker").textContent = `${language.label} · ${language.system} ${data.metadata.level}`;
  $("#article-title").textContent = data.analysis.title || data.article.title || "阅读练习";
  $("#article-summary").textContent = data.analysis.summary;
  $("#quality-score").textContent = `${Math.round(data.metadata.quality_score * 100)}%`;
  $("#topic-list").innerHTML = data.analysis.topics.map((topic) => `<span>${escapeHtml(topic)}</span>`).join("");
  $("#article-copy").innerHTML = data.article.sentences.map((sentence) => `<p class="article-sentence"><span class="sentence-id">${escapeHtml(sentence.id)}</span>${escapeHtml(sentence.text)}</p>`).join("");
  renderVocabulary(data.analysis.vocabulary_targets || []);
  selectResultTab("practice");
  renderQuestion();
}

function renderVocabulary(items) {
  if (!items.length) {
    $("#vocabulary-list").innerHTML = '<div class="empty-list">本次分析没有独立词汇目标</div>';
    return;
  }
  $("#vocabulary-list").innerHTML = items.map((item) => `
    <article class="vocabulary-item">
      <div class="vocabulary-word"><strong>${escapeHtml(item.surface)}</strong><small>${escapeHtml(item.reading || item.lemma || item.part_of_speech || "")}</small></div>
      <div class="vocabulary-meaning">${escapeHtml(item.meaning_in_context)}</div>
      <span class="level-badge">${escapeHtml(item.estimated_level)}</span>
    </article>`).join("");
}

function renderQuestion() {
  const questions = state.package.questions;
  const question = questions[state.questionIndex];
  const submitted = Boolean(state.submitted[question.id]);
  const selected = state.answers[question.id];
  $("#question-position").textContent = `第 ${state.questionIndex + 1} 题 / ${questions.length}`;
  $("#question-skill").textContent = question.skill;
  $("#question-type").textContent = typeLabels[question.type] || question.type;
  $("#question-prompt").textContent = question.prompt;
  $("#question-furigana").textContent = question.furigana || "";
  $("#question-furigana").hidden = !question.furigana;
  $("#quiz-progress").style.width = `${((state.questionIndex + (submitted ? 1 : 0)) / questions.length) * 100}%`;
  $("#score-display").textContent = `${Object.values(state.scores).filter(Boolean).length} / ${Object.keys(state.submitted).length}`;
  $("#previous-question").disabled = state.questionIndex === 0;
  $("#next-question").textContent = submitted ? (state.questionIndex === questions.length - 1 ? "完成练习" : "下一题") : "提交答案";
  $("#next-question").disabled = !submitted && !selected;

  if (question.options?.length) {
    $("#answer-options").innerHTML = question.options.map((option) => {
      const classes = ["answer-option"];
      if (selected === option.id) classes.push("selected");
      if (submitted && option.id === question.correct_option_id) classes.push("correct");
      if (submitted && selected === option.id && option.id !== question.correct_option_id) classes.push("incorrect");
      return `<button class="${classes.join(" ")}" type="button" data-option-id="${escapeHtml(option.id)}" ${submitted ? "disabled" : ""}><span class="option-id">${escapeHtml(option.id)}</span><span class="option-text">${escapeHtml(option.text)}</span></button>`;
    }).join("");
  } else {
    $("#answer-options").innerHTML = `<textarea class="short-answer-input" id="short-answer" placeholder="输入你的答案..." ${submitted ? "disabled" : ""}>${escapeHtml(selected || "")}</textarea>`;
  }

  const feedback = $("#feedback");
  feedback.hidden = !submitted;
  if (submitted) {
    const correct = state.scores[question.id];
    feedback.classList.toggle("incorrect", !correct);
    $("#feedback-title").textContent = correct ? "回答正确" : `正确答案：${correctAnswerText(question)}`;
    $("#answer-explanation").textContent = question.explanation;
    $("#evidence-quote").textContent = question.evidence_quote;
  }
}

function correctAnswerText(question) {
  if (question.options?.length) return question.options.find((option) => option.id === question.correct_option_id)?.text || question.correct_option_id;
  return question.accepted_answers.join(" / ");
}

function normalizeAnswer(value) {
  return String(value || "").trim().toLocaleLowerCase().replace(/[\s。！？.,!?]+$/u, "");
}

function submitOrAdvance() {
  const questions = state.package.questions;
  const question = questions[state.questionIndex];
  if (!state.submitted[question.id]) {
    const selected = state.answers[question.id];
    const correct = question.options?.length
      ? selected === question.correct_option_id
      : question.accepted_answers.some((answer) => normalizeAnswer(answer) === normalizeAnswer(selected));
    state.submitted[question.id] = true;
    state.scores[question.id] = correct;
    renderQuestion();
    return;
  }
  if (state.questionIndex < questions.length - 1) {
    state.questionIndex += 1;
    renderQuestion();
  } else {
    showToast(`练习完成：${Object.values(state.scores).filter(Boolean).length} / ${questions.length}`);
    selectResultTab("article");
  }
}

function selectResultTab(name) {
  $$(".result-tab").forEach((button) => button.classList.toggle("active", button.dataset.resultTab === name));
  $("#practice-panel").hidden = name !== "practice";
  $("#article-panel").hidden = name !== "article";
  $("#vocabulary-panel").hidden = name !== "vocabulary";
}

function exportJson() {
  const blob = new Blob([JSON.stringify(state.package, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `polyglot-quiz-${Date.now()}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
  showToast("JSON 已导出");
}

function clearResult() {
  state.package = null;
  $("#quiz-view").hidden = true;
  $("#empty-state").hidden = false;
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => { toast.hidden = true; }, 2600);
}

function updateServiceStatus() {
  const status = $("#service-status");
  if (state.providerSettings) {
    status.className = "service-status online";
    status.innerHTML = "<span></span>模型已配置";
  } else if (state.defaultProvider?.configured) {
    status.className = "service-status online";
    status.innerHTML = `<span></span>默认：${escapeHtml(state.defaultProvider.model)}`;
  } else {
    const demo = state.runtimeMode === "demo";
    status.className = `service-status ${demo ? "demo" : "online"}`;
    status.innerHTML = `<span></span>${demo ? "演示模式" : "服务正常"}`;
  }
  $("#open-model-settings").classList.toggle("configured", Boolean(state.providerSettings));
}

function openModelSettings() {
  const settings = state.providerSettings;
  if (settings) {
    $("#model-base-url").value = settings.baseUrl;
    $("#model-name").value = settings.model;
    $("#model-compatibility-mode").value = settings.compatibilityMode;
    $("#allow-insecure-http").checked = settings.allowInsecureHttp;
    $("#model-api-key").value = "";
    $("#model-api-key").placeholder = "已配置，留空保持不变";
  } else if (state.defaultProvider?.configured) {
    $("#model-base-url").value = state.defaultProvider.base_url;
    $("#model-name").value = state.defaultProvider.model;
    $("#model-compatibility-mode").value = state.defaultProvider.compatibility_mode || "auto";
    $("#allow-insecure-http").checked = state.defaultProvider.allow_insecure_http;
    $("#model-api-key").value = "";
    $("#model-api-key").placeholder = "重新保存时请输入 API Key";
  }
  $("#default-provider-status").textContent = state.defaultProvider?.configured
    ? `本机默认：${state.defaultProvider.model} · ${state.defaultProvider.base_url}`
    : "尚未保存本机默认模型";
  $("#clear-model-settings").disabled = !state.defaultProvider?.configured;
  $("#model-settings-error").hidden = true;
  updateInsecureHttpField();
  $("#model-settings-dialog").showModal();
}

async function saveModelSettings(persist = false) {
  const baseUrl = $("#model-base-url").value.trim().replace(/\/$/, "");
  const model = $("#model-name").value.trim();
  const enteredKey = $("#model-api-key").value.trim();
  const apiKey = enteredKey || state.providerSettings?.apiKey || "";
  const allowInsecureHttp = $("#allow-insecure-http").checked;
  const compatibilityMode = $("#model-compatibility-mode").value;
  let error = "";
  try {
    const parsed = new URL(baseUrl);
    if (!["http:", "https:"].includes(parsed.protocol) || parsed.search || parsed.hash) {
      error = "Base URL 必须是无查询参数的 HTTP(S) 地址。";
    } else if (parsed.protocol === "http:" && !allowInsecureHttp) {
      error = "使用 HTTP 地址前，请确认允许明文 HTTP。";
    }
  } catch {
    error = "请输入有效的 Base URL。";
  }
  if (!model) error = "请输入模型名称。";
  if (!apiKey) error = "请输入 API Key。";
  $("#model-settings-error").textContent = error;
  $("#model-settings-error").hidden = !error;
  if (error) return;
  const settings = {
    baseUrl,
    model,
    apiKey,
    allowInsecureHttp: baseUrl.startsWith("http://"),
    compatibilityMode,
  };
  if (persist) {
    try {
      const response = await fetch("/v1/provider-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: settings.apiKey,
          model: settings.model,
          base_url: settings.baseUrl,
          allow_insecure_http: settings.allowInsecureHttp,
          compatibility_mode: settings.compatibilityMode,
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(parseError(body, response.status));
      state.defaultProvider = body;
    } catch (caught) {
      $("#model-settings-error").textContent = caught.message || "默认模型保存失败。";
      $("#model-settings-error").hidden = false;
      return;
    }
  }
  state.providerSettings = persist ? null : settings;
  $("#model-api-key").value = "";
  $("#model-api-key").placeholder = "已配置，留空保持不变";
  $("#model-settings-dialog").close();
  updateServiceStatus();
  showToast(persist ? `已保存默认模型：${model}` : `本次使用模型：${model}`);
}

async function clearModelSettings() {
  try {
    const response = await fetch("/v1/provider-settings", { method: "DELETE" });
    if (!response.ok) throw new Error("清除默认模型失败");
    state.defaultProvider = await response.json();
  } catch (caught) {
    $("#model-settings-error").textContent = caught.message;
    $("#model-settings-error").hidden = false;
    return;
  }
  state.providerSettings = null;
  $("#model-name").value = "";
  $("#model-api-key").value = "";
  $("#model-api-key").placeholder = "输入 API Key";
  $("#allow-insecure-http").checked = false;
  $("#provider-preset").value = "openai";
  $("#model-compatibility-mode").value = "auto";
  $("#model-base-url").value = providerPresets.openai;
  $("#model-settings-dialog").close();
  updateServiceStatus();
  showToast("本机默认模型已清除");
}

async function checkHealth() {
  const status = $("#service-status");
  try {
    const [healthResponse, configResponse] = await Promise.all([fetch("/health"), fetch("/v1/config")]);
    if (!healthResponse.ok || !configResponse.ok) throw new Error();
    const config = await configResponse.json();
    const demo = config.runtime_mode === "demo";
    state.runtimeMode = demo ? "demo" : "production";
    state.defaultProvider = config.default_provider || { configured: false };
    document.documentElement.dataset.runtimeMode = state.runtimeMode;
    updateServiceStatus();
    if (demo) $("#load-sample").textContent = "载入演示文章";
  } catch {
    status.className = "service-status offline";
    status.innerHTML = "<span></span>服务离线";
  }
}

function initializeEvents() {
  $("#quiz-form").addEventListener("submit", generateQuiz);
  $$('[data-source-mode]').forEach((button) => button.addEventListener("click", () => setSourceMode(button.dataset.sourceMode)));
  $$(".language-option").forEach((button) => button.addEventListener("click", () => setLanguage(button.dataset.language)));
  $("#source-text").addEventListener("input", () => { $("#source-counter").textContent = `${$("#source-text").value.length} 字符`; });
  $("#question-blueprint").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-delta]");
    if (!button) return;
    const stepper = button.closest(".stepper");
    const type = stepper.dataset.questionType;
    state.counts[type] = Math.max(0, Math.min(10, state.counts[type] + Number(button.dataset.delta)));
    stepper.querySelector("output").textContent = state.counts[type];
    updateTotal();
  });
  $("#load-sample").addEventListener("click", () => {
    setSourceMode("text");
    $("#source-text").value = sampleArticles[state.language];
    $("#source-text").dispatchEvent(new Event("input"));
    $("#source-text").focus();
    showToast("示例文章已载入");
  });
  $("#answer-options").addEventListener("click", (event) => {
    const button = event.target.closest("[data-option-id]");
    if (!button) return;
    const question = state.package.questions[state.questionIndex];
    state.answers[question.id] = button.dataset.optionId;
    renderQuestion();
  });
  $("#answer-options").addEventListener("input", (event) => {
    if (event.target.id !== "short-answer") return;
    const question = state.package.questions[state.questionIndex];
    state.answers[question.id] = event.target.value;
    $("#next-question").disabled = !event.target.value.trim();
  });
  $("#next-question").addEventListener("click", submitOrAdvance);
  $("#previous-question").addEventListener("click", () => {
    if (state.questionIndex > 0) { state.questionIndex -= 1; renderQuestion(); }
  });
  $$(".result-tab").forEach((button) => button.addEventListener("click", () => selectResultTab(button.dataset.resultTab)));
  $("#export-json").addEventListener("click", exportJson);
  $("#clear-result").addEventListener("click", clearResult);
  $("#open-model-settings").addEventListener("click", openModelSettings);
  $("#close-model-settings").addEventListener("click", () => $("#model-settings-dialog").close());
  $("#apply-model-settings").addEventListener("click", () => saveModelSettings(false));
  $("#save-model-settings").addEventListener("click", () => saveModelSettings(true));
  $("#clear-model-settings").addEventListener("click", clearModelSettings);
  $("#provider-preset").addEventListener("change", (event) => {
    if (event.target.value === "custom") $("#model-base-url").value = "";
    else $("#model-base-url").value = providerPresets[event.target.value];
    updateInsecureHttpField();
  });
  $("#model-base-url").addEventListener("input", updateInsecureHttpField);
  $("#toggle-api-key").addEventListener("click", () => {
    const input = $("#model-api-key");
    input.type = input.type === "password" ? "text" : "password";
    $("#toggle-api-key").textContent = input.type === "password" ? "显示" : "隐藏";
  });
  $("#model-settings-dialog").addEventListener("click", (event) => {
    if (event.target === $("#model-settings-dialog")) $("#model-settings-dialog").close();
  });
}

function updateInsecureHttpField() {
  const insecure = $("#model-base-url").value.trim().toLowerCase().startsWith("http://");
  $("#insecure-http-field").hidden = !insecure;
  if (!insecure) $("#allow-insecure-http").checked = false;
}

renderBlueprint();
setLanguage("en");
initializeEvents();
checkHealth();
