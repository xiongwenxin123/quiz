const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const languageConfig = {
  en: { label: "CEFR 难度", levels: ["A1", "A2", "B1", "B2", "C1", "C2"], initial: "B1" },
  ja: { label: "JLPT 难度", levels: ["N5", "N4", "N3", "N2", "N1"], initial: "N3" },
  es: { label: "CEFR 难度", levels: ["A1", "A2", "B1", "B2", "C1", "C2"], initial: "B1" },
};

const presets = {
  siliconflow: "https://api.siliconflow.cn/v1",
  openai: "https://api.openai.com/v1",
};

const sample = `Many cities are planting trees to reduce summer heat. Trees shade streets and release water vapor, which can lower nearby temperatures.

However, urban trees need careful planning because roots may damage sidewalks and young trees require regular watering. Researchers recommend choosing native species and planting them where residents receive the greatest benefit.

A successful program therefore combines environmental goals with long-term maintenance.`;

const questionTypes = ["main_idea", "detail", "inference", "vocabulary_context", "grammar", "author_purpose", "true_false", "cloze", "short_answer"];
const state = {
  sourceMode: "text",
  language: "en",
  provider: null,
  defaultProvider: null,
  runtimeMode: "production",
  jobId: null,
  timer: null,
  snapshot: null,
  renderedVocabulary: 0,
  renderedQuestions: 0,
  renderedQuestionErrors: 0,
  pollFailures: 0,
};

function escapeHtml(value = "") {
  return String(value).replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[character]));
}

function setLanguage(language) {
  state.language = language;
  $$("[data-language]").forEach((button) => button.classList.toggle("active", button.dataset.language === language));
  const config = languageConfig[language];
  $("#level-label").textContent = config.label;
  $("#level-select").innerHTML = config.levels.map((level) => `<option${level === config.initial ? " selected" : ""}>${level}</option>`).join("");
}

function setSourceMode(mode) {
  state.sourceMode = mode;
  $$('[data-source]').forEach((button) => {
    const active = button.dataset.source === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  $("#text-panel").hidden = mode !== "text";
  $("#url-panel").hidden = mode !== "url";
  $("#source-text").required = mode === "text";
  $("#source-url").required = mode === "url";
}

function buildRequest() {
  const total = Number($("#question-count").value);
  return {
    ...(state.sourceMode === "text" ? { source_text: $("#source-text").value.trim() } : { source_url: $("#source-url").value.trim() }),
    target_language: state.language,
    level: $("#level-select").value,
    explanation_language: "zh-CN",
    question_counts: questionTypes.slice(0, total).map((type) => ({ type, count: 1 })),
    include_furigana: true,
    max_repair_attempts: 1,
  };
}

function providerHeaders(requestId) {
  const headers = { "Content-Type": "application/json", "X-Quiz-Request-ID": requestId };
  if (state.provider) {
    headers["X-Quiz-LLM-API-Key"] = state.provider.apiKey;
    headers["X-Quiz-LLM-Model"] = state.provider.model;
    headers["X-Quiz-LLM-Base-URL"] = state.provider.baseUrl;
    headers["X-Quiz-LLM-Compatibility"] = state.provider.compatibilityMode;
    if (state.provider.allowHttp) headers["X-Quiz-Allow-Insecure-HTTP"] = "true";
  }
  return headers;
}

function requestId() {
  if (crypto?.randomUUID) return crypto.randomUUID().replaceAll("-", "");
  return `${Date.now()}${Math.random().toString(16).slice(2)}`;
}

async function startJob(event) {
  event.preventDefault();
  const request = buildRequest();
  let error = "";
  if (state.sourceMode === "text" && request.source_text.length < 80) error = "正文至少需要 80 个字符。";
  if (state.sourceMode === "url" && !request.source_url) error = "请输入文章链接。";
  $("#compose-error").textContent = error;
  $("#compose-error").hidden = !error;
  if (error) return;

  resetStreams();
  state.jobId = requestId();
  showReader();
  try {
    const response = await fetch("/v1/progressive-quizzes", {
      method: "POST",
      headers: providerHeaders(state.jobId),
      body: JSON.stringify(request),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(parseError(body, response.status));
    pollJob();
  } catch (caught) {
    showJobError(caught.message || "任务创建失败");
    if (/model|模型|API|default/i.test(caught.message || "")) openSettings();
  }
}

async function pollJob() {
  if (!state.jobId) return;
  try {
    const response = await fetch(`/v1/progressive-quizzes/${encodeURIComponent(state.jobId)}`, { cache: "no-store" });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(parseError(body, response.status));
    state.snapshot = body;
    state.pollFailures = 0;
    renderSnapshot(body);
    if (!body.done) state.timer = setTimeout(pollJob, 650);
  } catch (caught) {
    state.pollFailures += 1;
    if (state.pollFailures < 4 && state.jobId) {
      state.timer = setTimeout(pollJob, 1200);
      return;
    }
    showJobError(caught.message || "任务状态读取失败");
  }
}

function renderSnapshot(job) {
  $("#job-message").textContent = job.message;
  $("#job-percent").textContent = `${job.percent}%`;
  $("#job-progress").style.width = `${job.percent}%`;
  $("#question-progress").textContent = `${job.questions.length} / ${job.requested_total}`;
  $("#job-status").classList.toggle("failed", job.failed);
  if (job.article) renderArticle(job.article, job.analysis);
  appendVocabulary(job.vocabulary || []);
  appendQuestions(job.questions || []);
  appendQuestionErrors(job.question_errors || []);
  if (job.failed) showJobError(job.error || "生成未能完成，已保留现有内容。");
  if (job.done && !job.failed) showToast("本次精读已生成完成");
}

function renderArticle(article, analysis) {
  $("#article-title").textContent = analysis?.title || article.title || "文章精读";
  $("#article-summary").textContent = analysis?.summary || "文章教学生成中，原文已可以阅读。";
  const teaching = Object.fromEntries((analysis?.paragraph_teaching || []).map((item) => [item.paragraph_id, item]));
  $("#article-content").innerHTML = (article.paragraphs || []).map((paragraph, index) => {
    const item = teaching[paragraph.id];
    return `<section class="teaching-paragraph ${item ? "" : "source-only"}">
      <span class="paragraph-index">P${String(index + 1).padStart(2, "0")}</span>
      <p class="original-copy">${escapeHtml(paragraph.text)}</p>
      ${item ? `<div class="translation-block"><strong>中文翻译</strong><p>${escapeHtml(item.translation_zh)}</p></div>
      <div class="teaching-notes">
        ${noteList("词汇提示", item.vocabulary_notes_zh)}
        ${noteList("语法提示", item.grammar_notes_zh)}
      </div>
      ${item.discourse_note_zh ? `<div class="teaching-note"><span>篇章作用</span><p>${escapeHtml(item.discourse_note_zh)}</p></div>` : ""}
      ${item.author_intent_zh ? `<div class="teaching-note"><span>表达意图</span><p>${escapeHtml(item.author_intent_zh)}</p></div>` : ""}` : ""}
    </section>`;
  }).join("");
}

function noteList(label, values = []) {
  if (!values.length) return "";
  return `<div><strong>${label}</strong><ul>${values.map((value) => `<li>${escapeHtml(value)}</li>`).join("")}</ul></div>`;
}

function appendVocabulary(items) {
  if (items.length && state.renderedVocabulary === 0) $("#vocabulary-list").innerHTML = "";
  for (const item of items.slice(state.renderedVocabulary)) {
    $("#vocabulary-list").insertAdjacentHTML("beforeend", `<article class="vocabulary-card">
      <div class="word-head"><strong>${escapeHtml(item.surface)}</strong><small>${escapeHtml(item.estimated_level)}</small></div>
      ${item.reading ? `<p class="word-reading">${escapeHtml(item.reading)}</p>` : ""}
      <p class="word-meaning">${escapeHtml(item.meaning_in_context)}</p>
      <p class="word-context">${escapeHtml(item.source_excerpt)}</p>
    </article>`);
  }
  state.renderedVocabulary = items.length;
  $("#vocabulary-count").textContent = String(items.length);
}

function appendQuestions(items) {
  if (items.length && state.renderedQuestions === 0) $("#question-list").innerHTML = "";
  for (const question of items.slice(state.renderedQuestions)) {
    $("#question-list").insertAdjacentHTML("beforeend", questionMarkup(question, state.renderedQuestions + 1));
    state.renderedQuestions += 1;
  }
}

function questionMarkup(question, number) {
  const answers = question.options?.length
    ? `<div class="answer-list">${question.options.map((option) => `<button class="answer-option" type="button" data-question="${escapeHtml(question.id)}" data-option="${escapeHtml(option.id)}" data-correct="${option.id === question.correct_option_id}"><span>${escapeHtml(option.id)}</span><span>${escapeHtml(option.text)}</span></button>`).join("")}</div>`
    : `<textarea class="open-answer" data-open-answer="${escapeHtml(question.id)}" placeholder="写下你的回答..."></textarea><button class="reveal-answer" type="button" data-reveal="${escapeHtml(question.id)}">查看参考与解析</button>`;
  return `<article class="question-card" data-question-card="${escapeHtml(question.id)}">
    <div class="question-kicker"><span>第 ${number} 题</span><span>${escapeHtml(question.type)}</span></div>
    <h3>${escapeHtml(question.prompt)}</h3>${answers}
    <div class="answer-feedback" hidden><strong>解析</strong><br>${escapeHtml(question.explanation)}${question.accepted_answers?.length ? `<br><strong>参考：</strong>${escapeHtml(question.accepted_answers.join("；"))}` : ""}</div>
  </article>`;
}

function appendQuestionErrors(items) {
  for (const item of items.slice(state.renderedQuestionErrors)) {
    $("#question-errors").insertAdjacentHTML("beforeend", `<div class="question-error">${escapeHtml(item.message)}</div>`);
  }
  state.renderedQuestionErrors = items.length;
}

function resetStreams() {
  clearTimeout(state.timer);
  state.snapshot = null;
  state.renderedVocabulary = 0;
  state.renderedQuestions = 0;
  state.renderedQuestionErrors = 0;
  state.pollFailures = 0;
  $("#article-title").textContent = "文章解析中";
  $("#article-summary").textContent = "原文准备好后会先显示在这里。";
  $("#article-content").innerHTML = '<div class="skeleton-block"><span></span><span></span><span></span></div>';
  $("#vocabulary-list").innerHTML = '<p class="pending-copy">文章教学完成后继续生成</p>';
  $("#question-list").innerHTML = '<p class="pending-copy">题目将在后台逐题出现</p>';
  $("#question-errors").innerHTML = "";
  $("#vocabulary-count").textContent = "0";
  $("#question-progress").textContent = `0 / ${$("#question-count").value}`;
  $("#job-error").hidden = true;
  $("#job-status").classList.remove("failed");
  $("#job-progress").style.width = "1%";
}

function showReader() {
  $("#compose-view").hidden = true;
  $("#reader-view").hidden = false;
  $("#header-back").hidden = false;
  $("#page-title").textContent = "文章精读";
  window.scrollTo({ top: 0, behavior: "auto" });
}

function showCompose() {
  clearTimeout(state.timer);
  state.jobId = null;
  $("#reader-view").hidden = true;
  $("#compose-view").hidden = false;
  $("#header-back").hidden = true;
  $("#page-title").textContent = "精读小课";
  window.scrollTo({ top: 0, behavior: "auto" });
}

function showJobError(message) {
  $("#job-error").textContent = message;
  $("#job-error").hidden = false;
  $("#job-status").classList.add("failed");
  $("#job-message").textContent = "生成遇到问题";
}

function parseError(body, status) {
  if (typeof body?.detail === "string") return body.detail;
  if (body?.detail?.message) return body.detail.message;
  if (Array.isArray(body?.detail)) return body.detail.map((item) => item.msg).join("；");
  return `请求失败（HTTP ${status}）`;
}

function openSettings() {
  const current = state.provider || state.defaultProvider;
  if (current?.configured || state.provider) {
    $("#model-base-url").value = current.baseUrl || current.base_url || presets.siliconflow;
    $("#model-name").value = current.model || "";
    $("#compatibility-mode").value = current.compatibilityMode || current.compatibility_mode || "auto";
  }
  $("#settings-error").hidden = true;
  $("#settings-dialog").showModal();
}

async function saveSettings(persist) {
  const enteredKey = $("#model-api-key").value.trim();
  const apiKey = enteredKey || state.provider?.apiKey || "";
  const settings = {
    apiKey,
    model: $("#model-name").value.trim(),
    baseUrl: $("#model-base-url").value.trim().replace(/\/$/, ""),
    compatibilityMode: $("#compatibility-mode").value,
    allowHttp: $("#allow-http").checked,
  };
  let error = "";
  try {
    const parsed = new URL(settings.baseUrl);
    if (!["http:", "https:"].includes(parsed.protocol)) error = "Base URL 必须是 HTTP(S) 地址。";
    if (parsed.protocol === "http:" && !settings.allowHttp) error = "使用 HTTP 前请确认允许明文连接。";
  } catch { error = "Base URL 格式不正确。"; }
  if (!settings.model) error = "请输入模型名称。";
  if (!settings.apiKey) error = "请输入 API Key。";
  if (error) {
    $("#settings-error").textContent = error;
    $("#settings-error").hidden = false;
    return;
  }
  if (persist) {
    try {
      const response = await fetch("/v1/provider-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: settings.apiKey, model: settings.model, base_url: settings.baseUrl, allow_insecure_http: settings.allowHttp, compatibility_mode: settings.compatibilityMode }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(parseError(body, response.status));
      state.defaultProvider = body;
      state.provider = null;
    } catch (caught) {
      $("#settings-error").textContent = caught.message;
      $("#settings-error").hidden = false;
      return;
    }
  } else {
    state.provider = settings;
  }
  $("#model-api-key").value = "";
  $("#settings-dialog").close();
  showToast(persist ? "默认模型已保存" : "本次模型已启用");
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => { toast.hidden = true; }, 2200);
}

async function initialize() {
  setLanguage("en");
  try {
    const response = await fetch("/v1/config");
    const config = await response.json();
    state.defaultProvider = config.default_provider;
    state.runtimeMode = config.runtime_mode;
    if (config.runtime_mode === "demo") $("#question-count").value = "9";
  } catch { /* The start action will surface service errors. */ }

  $("#miniapp-form").addEventListener("submit", startJob);
  $$('[data-source]').forEach((button) => button.addEventListener("click", () => setSourceMode(button.dataset.source)));
  $$('[data-language]').forEach((button) => button.addEventListener("click", () => setLanguage(button.dataset.language)));
  $("#source-text").addEventListener("input", () => { $("#source-count").textContent = `${$("#source-text").value.length} 字符`; });
  $("#load-sample").addEventListener("click", () => { $("#source-text").value = sample; $("#source-text").dispatchEvent(new Event("input")); });
  $("#header-back").addEventListener("click", showCompose);
  $("#capsule-home").addEventListener("click", showCompose);
  $("#open-settings").addEventListener("click", openSettings);
  $("#close-settings").addEventListener("click", () => $("#settings-dialog").close());
  $("#provider-preset").addEventListener("change", (event) => { if (presets[event.target.value]) $("#model-base-url").value = presets[event.target.value]; });
  $("#save-session").addEventListener("click", () => saveSettings(false));
  $("#save-default").addEventListener("click", () => saveSettings(true));
  $("#question-list").addEventListener("click", (event) => {
    const option = event.target.closest(".answer-option");
    const reveal = event.target.closest("[data-reveal]");
    if (option) {
      const card = option.closest(".question-card");
      card.querySelectorAll(".answer-option").forEach((button) => {
        button.disabled = true;
        if (button.dataset.correct === "true") button.classList.add("correct");
      });
      if (option.dataset.correct !== "true") option.classList.add("incorrect");
      card.querySelector(".answer-feedback").hidden = false;
    }
    if (reveal) reveal.closest(".question-card").querySelector(".answer-feedback").hidden = false;
  });
  $$('[data-tab]').forEach((button) => button.addEventListener("click", () => {
    $$('[data-tab]').forEach((item) => item.classList.toggle("active", item === button));
    if (button.dataset.tab === "new") showCompose();
    if (button.dataset.tab === "settings") openSettings();
    if (button.dataset.tab === "study" && state.jobId) showReader();
  }));
}

initialize();
