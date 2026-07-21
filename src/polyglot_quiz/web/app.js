const languageDefaults = {
  en: { label: "EN", system: "CEFR", levels: ["A1", "A2", "B1", "B2", "C1", "C2"], defaultLevel: "B1" },
  ja: { label: "JA", system: "JLPT", levels: ["N5", "N4", "N3", "N2", "N1"], defaultLevel: "N3" },
  es: { label: "ES", system: "CEFR", levels: ["A1", "A2", "B1", "B2", "C1", "C2"], defaultLevel: "B1" },
};

const questionTypeGroups = [
  {
    id: "basic", label: "基础理解", hint: "定位、匹配与信息提取", open: true,
    items: [
      { id: "detail", label: "细节事实", hint: "人物、时间、地点、原因", count: 1 },
      { id: "true_false", label: "正误判断", hint: "True / False", count: 1 },
      { id: "true_false_not_given", label: "T / F / NG", hint: "含 Not Given", count: 0 },
      { id: "reference", label: "词义指代", hint: "it / this 指向内容", count: 0 },
      { id: "information_matching", label: "信息匹配", hint: "段落、人物或事件匹配", count: 0 },
      { id: "summary_completion", label: "摘要填空", hint: "限定词数提取答案", count: 0 },
      { id: "short_answer", label: "信息简答", hint: "简短提取原文信息", count: 1 },
      { id: "chart_completion", label: "图表流程填空", hint: "原因、结果或流程节点", count: 0 },
      { id: "event_ordering", label: "事件排序", hint: "时间线与步骤顺序", count: 0 },
    ],
  },
  {
    id: "logic", label: "深层逻辑", hint: "主旨、结构、态度与推理", open: false,
    items: [
      { id: "main_idea", label: "全文主旨", hint: "中心思想或最佳标题", count: 1 },
      { id: "paragraph_main_idea", label: "段落主旨", hint: "指定段落核心内容", count: 0 },
      { id: "text_structure", label: "文章结构", hint: "时间、对比、问题解决", count: 0 },
      { id: "paragraph_function", label: "段落作用", hint: "引入、转折、论证、总结", count: 0 },
      { id: "inference", label: "推理判断", hint: "文本强支持的结论", count: 1 },
      { id: "author_attitude", label: "作者态度", hint: "支持、批判、中立或怀疑", count: 0 },
      { id: "author_purpose", label: "写作目的", hint: "例子、引语或细节的作用", count: 1 },
      { id: "logical_relationship", label: "隐含逻辑", hint: "因果、对比、递进、举例", count: 0 },
    ],
  },
  {
    id: "language", label: "语言词汇", hint: "词义、语法、翻译与改写", open: false,
    items: [
      { id: "vocabulary_context", label: "语境词义", hint: "生词在原文中的含义", count: 1 },
      { id: "cloze", label: "语境完形", hint: "词汇、搭配与衔接", count: 1 },
      { id: "grammar", label: "语法挖空", hint: "时态、非谓语、从句等", count: 1 },
      { id: "sentence_translation", label: "长难句翻译", hint: "原文句子译为中文", count: 0 },
      { id: "sentence_rewrite", label: "句子改写", hint: "保持原意进行转述", count: 0 },
      { id: "collocation_extraction", label: "搭配提取", hint: "提取固定搭配并运用", count: 0 },
      { id: "translation_to_target", label: "中译外", hint: "使用原文词汇句式翻译", count: 0 },
      { id: "paragraph_translation", label: "段落翻译", hint: "完整翻译指定段落", count: 0 },
      { id: "question_formation", label: "划线提问", hint: "针对信息写特殊疑问句", count: 0 },
    ],
  },
  {
    id: "writing", label: "写作输出", hint: "概括、转述与读后写作", open: false,
    items: [
      { id: "paragraph_summary", label: "段落概括", hint: "限定词数概括一段", count: 0 },
      { id: "article_summary", label: "全文摘要", hint: "整篇内容压缩表达", count: 0 },
      { id: "paraphrase", label: "观点转述", hint: "用自己的话解释结论", count: 0 },
      { id: "reflection_writing", label: "读后感", hint: "联系原文进行反思", count: 0 },
      { id: "argument_writing", label: "议论文", hint: "同意或反对并给出理由", count: 0 },
      { id: "letter_writing", label: "书信写作", hint: "给人物或机构写建议信", count: 0 },
      { id: "retelling", label: "复述", hint: "复述故事、过程或研究", count: 0 },
      { id: "comparison_writing", label: "对比写作", hint: "原文观点与经验比较", count: 0 },
    ],
  },
  {
    id: "critical", label: "思辨拓展", hint: "评价、迁移、研究与方案", open: false,
    items: [
      { id: "critical_response", label: "观点评价", hint: "是否同意作者并说明理由", count: 0 },
      { id: "real_world_connection", label: "现实联系", hint: "联系生活中的类似问题", count: 0 },
      { id: "research_extension", label: "研究拓展", hint: "设计可行的后续研究", count: 0 },
      { id: "solution_proposal", label: "解决方案", hint: "针对问题提出具体建议", count: 0 },
    ],
  },
];
const questionTypes = questionTypeGroups.flatMap((group) => group.items);

const typeLabels = Object.fromEntries(questionTypes.map((item) => [item.id, item.label]));
const sampleArticles = {
  en: "Many cities are planting trees to reduce summer heat. Trees shade streets and release water vapor, which can lower nearby temperatures.\n\nHowever, urban trees need careful planning because roots may damage sidewalks and young trees require regular watering. Researchers recommend choosing native species and planting them where residents receive the greatest benefit.\n\nA successful program therefore combines environmental goals with long-term maintenance.",
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
  grades: {},
  grading: {},
  gradeErrors: {},
  progressTimer: null,
  activeRequestId: null,
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
  $("#question-blueprint").innerHTML = questionTypeGroups.map((group) => `
    <details class="blueprint-group" data-question-group="${group.id}" ${group.open ? "open" : ""}>
      <summary><span><strong>${group.label}</strong><small>${group.hint}</small></span><output data-group-count="${group.id}">0</output></summary>
      <div class="blueprint-group-items">${group.items.map((item) => `
        <div class="blueprint-row">
          <div class="blueprint-label"><strong>${item.label}</strong><small>${item.hint}</small></div>
          <div class="stepper" data-question-type="${item.id}">
            <button type="button" data-delta="-1" aria-label="减少${item.label}" title="减少">−</button>
            <output>${state.counts[item.id]}</output>
            <button type="button" data-delta="1" aria-label="增加${item.label}" title="增加">+</button>
          </div>
        </div>`).join("")}</div>
    </details>`).join("");
  updateTotal();
}

function updateTotal() {
  $("#question-total").textContent = Object.values(state.counts).reduce((sum, value) => sum + value, 0);
  questionTypeGroups.forEach((group) => {
    const selected = group.items.reduce((sum, item) => sum + state.counts[item.id], 0);
    const output = $(`[data-group-count="${group.id}"]`);
    output.textContent = `${selected} 题`;
    output.classList.toggle("selected", selected > 0);
  });
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
  if (request.question_counts.reduce((sum, item) => sum + item.count, 0) > 50) return "单次最多生成 50 道题。";
  if (state.sourceMode === "text" && request.source_text.length < 80) return "文章正文至少需要 80 个字符。";
  if (state.sourceMode === "url" && !request.source_url) return "请输入公开文章 URL。";
  return "";
}

function setLoading(loading, message = "正在提交生成请求...") {
  $("#generate-button").disabled = loading;
  $("#generate-button").classList.toggle("loading", loading);
  $("#empty-state").hidden = loading || Boolean(state.package);
  $("#loading-state").hidden = !loading;
  $("#quiz-view").hidden = loading || !state.package;
  if (loading) $("#loading-message").textContent = message;
}

function createRequestId() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID().replaceAll("-", "");
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`.padEnd(12, "0");
}

function stopProgressPolling(requestId) {
  if (requestId && state.activeRequestId !== requestId) return;
  clearTimeout(state.progressTimer);
  state.progressTimer = null;
  state.activeRequestId = null;
}

async function pollProgress(requestId) {
  if (state.activeRequestId !== requestId) return;
  try {
    const response = await fetch(`/v1/progress/${encodeURIComponent(requestId)}`, {
      cache: "no-store",
    });
    if (response.ok) {
      const progress = await response.json();
      if (state.activeRequestId !== requestId) return;
      $("#loading-message").textContent = progress.message;
      if (progress.done) return;
    }
  } catch {
    // The generation request remains authoritative; retry transient progress failures.
  }
  if (state.activeRequestId === requestId) {
    state.progressTimer = setTimeout(() => pollProgress(requestId), 600);
  }
}

function parseError(body, status) {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join("；");
  return `生成失败（HTTP ${status}）`;
}

function buildProviderHeaders(requestId) {
  const headers = {
    "Content-Type": "application/json",
    "X-Quiz-Request-ID": requestId,
  };
  if (state.providerSettings) {
    headers["X-Quiz-LLM-API-Key"] = state.providerSettings.apiKey;
    headers["X-Quiz-LLM-Model"] = state.providerSettings.model;
    headers["X-Quiz-LLM-Base-URL"] = state.providerSettings.baseUrl;
    headers["X-Quiz-LLM-Compatibility"] = state.providerSettings.compatibilityMode;
    if (state.providerSettings.allowInsecureHttp) headers["X-Quiz-Allow-Insecure-HTTP"] = "true";
  }
  return headers;
}

async function generateQuiz(event) {
  event.preventDefault();
  const request = buildRequest();
  const error = validateRequest(request);
  $("#form-error").hidden = !error;
  $("#form-error").textContent = error;
  if (error) return;

  state.package = null;
  const requestId = createRequestId();
  state.activeRequestId = requestId;
  setLoading(true);
  state.progressTimer = setTimeout(() => pollProgress(requestId), 150);
  try {
    const response = await fetch("/v1/quizzes", {
      method: "POST",
      headers: buildProviderHeaders(requestId),
      body: JSON.stringify(request),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(parseError(body, response.status));
    state.package = body;
    state.questionIndex = 0;
    state.answers = {};
    state.submitted = {};
    state.scores = {};
    state.grades = {};
    state.grading = {};
    state.gradeErrors = {};
    renderPackage();
  } catch (caught) {
    $("#form-error").textContent = caught.message || "生成失败，请检查服务配置。";
    $("#form-error").hidden = false;
    showToast("练习生成失败");
  } finally {
    stopProgressPolling(requestId);
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
  renderArticle(data.article, data.analysis.paragraph_teaching || []);
  renderVocabulary(data.analysis.vocabulary_targets || []);
  selectResultTab("practice");
  renderQuestion();
}

function renderArticle(article, teachingItems) {
  const teachingByParagraph = Object.fromEntries(teachingItems.map((item) => [item.paragraph_id, item]));
  const sentenceById = Object.fromEntries(article.sentences.map((sentence) => [sentence.id, sentence]));
  const paragraphs = article.paragraphs?.length
    ? article.paragraphs
    : article.sentences.map((sentence, index) => ({ id: `p${index + 1}`, text: sentence.text, sentence_ids: [sentence.id] }));
  $("#article-copy").innerHTML = paragraphs.map((paragraph, index) => {
    const teaching = teachingByParagraph[paragraph.id] || {};
    const original = paragraph.sentence_ids.map((id) => sentenceById[id]).filter(Boolean);
    const vocabularyNotes = teaching.vocabulary_notes_zh || [];
    const grammarNotes = teaching.grammar_notes_zh || [];
    return `
      <section class="teaching-paragraph">
        <header class="paragraph-heading"><span>${escapeHtml(paragraph.id)}</span><strong>第 ${index + 1} 段</strong></header>
        <div class="paragraph-original">
          ${original.map((sentence) => `<p class="article-sentence"><span class="sentence-id">${escapeHtml(sentence.id)}</span>${escapeHtml(sentence.text)}</p>`).join("")}
        </div>
        <div class="paragraph-translation">
          <span class="teaching-label">中文翻译</span>
          <p>${escapeHtml(teaching.translation_zh || "暂无翻译")}</p>
        </div>
        <div class="paragraph-teaching-grid">
          <div><span class="teaching-label">词汇</span>${renderTeachingNotes(vocabularyNotes)}</div>
          <div><span class="teaching-label">语法与文法</span>${renderTeachingNotes(grammarNotes)}</div>
          <div><span class="teaching-label">篇章作用</span><p>${escapeHtml(teaching.discourse_note_zh || "暂无解析")}</p></div>
          <div><span class="teaching-label">作者意图</span><p>${escapeHtml(teaching.author_intent_zh || "暂无解析")}</p></div>
        </div>
      </section>`;
  }).join("");
}

function renderTeachingNotes(items) {
  if (!items.length) return '<p class="muted-note">本段无独立讲解</p>';
  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderVocabulary(items) {
  if (!items.length) {
    $("#vocabulary-list").innerHTML = '<div class="empty-list">本次分析没有独立词汇目标</div>';
    return;
  }
  $("#vocabulary-list").innerHTML = items.map((item) => `
    <article class="vocabulary-item">
      <header class="vocabulary-header">
        <div class="vocabulary-word"><strong>${escapeHtml(item.surface)}</strong><small>${escapeHtml([item.reading, item.lemma, item.part_of_speech].filter(Boolean).join(" · "))}</small></div>
        <span class="level-badge">${escapeHtml(item.estimated_level)}</span>
      </header>
      <div class="vocabulary-section vocabulary-meaning"><span class="teaching-label">中文释义</span><p>${escapeHtml(item.meaning_in_context)}</p></div>
      <div class="vocabulary-section vocabulary-context"><span class="teaching-label">原文语境</span><blockquote>${escapeHtml(item.source_excerpt || "")}</blockquote></div>
      <div class="vocabulary-section"><span class="teaching-label">补充例句</span>
        <ol class="example-list">${(item.examples || []).map((example) => `<li><p>${escapeHtml(example.text)}</p><small>${escapeHtml(example.translation_zh)}</small></li>`).join("")}</ol>
      </div>
    </article>`).join("");
}

function renderQuestion() {
  const questions = state.package.questions;
  const question = questions[state.questionIndex];
  const submitted = Boolean(state.submitted[question.id]);
  const selected = state.answers[question.id];
  const selfReview = question.evaluation_mode === "self_review";
  $("#question-position").textContent = `第 ${state.questionIndex + 1} 题 / ${questions.length}`;
  $("#question-skill").textContent = question.skill;
  $("#question-type").textContent = typeLabels[question.type] || question.type;
  $("#question-prompt").textContent = question.prompt;
  $("#question-furigana").textContent = question.furigana || "";
  $("#question-furigana").hidden = !question.furigana;
  $("#quiz-progress").style.width = `${((state.questionIndex + (submitted ? 1 : 0)) / questions.length) * 100}%`;
  $("#score-display").textContent = scoreSummary();
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
    const limit = question.word_limit ? `建议不超过 ${question.word_limit} 词` : "输入你的答案...";
    const longResponse = selfReview || (question.word_limit || 0) > 80;
    $("#answer-options").innerHTML = `<textarea class="short-answer-input${longResponse ? " extended" : ""}" id="short-answer" placeholder="${escapeHtml(limit)}" ${submitted ? "disabled" : ""}>${escapeHtml(selected || "")}</textarea>`;
  }

  const feedback = $("#feedback");
  feedback.hidden = !submitted;
  if (submitted) {
    const correct = state.scores[question.id];
    feedback.classList.toggle("incorrect", !selfReview && !correct);
    feedback.classList.toggle("self-review", selfReview);
    $("#feedback-title").textContent = selfReview
      ? "请对照参考答案与评分要点自评"
      : correct ? "回答正确" : `正确答案：${correctAnswerText(question)}`;
    $("#reference-answer-block").hidden = !selfReview;
    $("#reference-answer").textContent = selfReview ? correctAnswerText(question) : "";
    $("#rubric-block").hidden = !selfReview || !(question.rubric || []).length;
    $("#answer-rubric").innerHTML = (question.rubric || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    const grading = Boolean(state.grading[question.id]);
    const grade = state.grades[question.id];
    const gradeError = state.gradeErrors[question.id];
    $("#ai-grade-actions").hidden = !selfReview;
    $("#ai-grade-button").disabled = grading;
    $("#ai-grade-button").textContent = grading ? "正在评分..." : grade ? "重新评分" : "AI 评分";
    $("#ai-grade-result").hidden = !selfReview || (!grade && !gradeError);
    $("#ai-grade-result").innerHTML = grade
      ? renderGradeResult(grade)
      : gradeError ? `<p class="grade-error">${escapeHtml(gradeError)}</p>` : "";
    $("#answer-explanation").textContent = question.explanation;
    $("#evidence-quote").textContent = question.evidence_quote;
  }
}

function renderGradeResult(grade) {
  const dimensions = grade.dimensions.map((item) => `
    <li>
      <div><strong>${escapeHtml(item.criterion)}</strong><span>${item.score} / 5</span></div>
      <div class="grade-meter"><span style="width:${item.score * 20}%"></span></div>
      <p>${escapeHtml(item.feedback)}</p>
    </li>`).join("");
  const list = (items) => `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
  return `
    <header class="grade-summary"><div><strong>${grade.total_score}</strong><span>/ ${grade.max_score}</span></div><p>${escapeHtml(grade.overall_feedback)}</p></header>
    <section><span class="grade-label">分项评分</span><ol class="grade-dimensions">${dimensions}</ol></section>
    <div class="grade-columns">
      <section><span class="grade-label">做得好的地方</span>${list(grade.strengths)}</section>
      <section><span class="grade-label">改进建议</span>${list(grade.improvements)}</section>
    </div>
    <section class="grade-revision"><span class="grade-label">优化示例</span><p>${escapeHtml(grade.revised_example)}</p></section>`;
}

function correctAnswerText(question) {
  if (question.options?.length) return question.options.find((option) => option.id === question.correct_option_id)?.text || question.correct_option_id;
  return question.accepted_answers.join(" / ");
}

function normalizeAnswer(value) {
  return String(value || "").trim().toLocaleLowerCase().replace(/[\s。！？.,!?]+$/u, "");
}

function scoreSummary() {
  const submittedIds = Object.keys(state.submitted);
  const autoScores = submittedIds.map((id) => state.scores[id]).filter((value) => value !== null && value !== undefined);
  const selfReviewed = submittedIds.length - autoScores.length;
  const autoText = `${autoScores.filter(Boolean).length} / ${autoScores.length}`;
  return selfReviewed ? `${autoText} · 自评 ${selfReviewed}` : autoText;
}

async function gradeOpenResponse() {
  const question = state.package.questions[state.questionIndex];
  if (!state.submitted[question.id] || question.evaluation_mode !== "self_review") return;
  const learnerAnswer = state.answers[question.id]?.trim();
  if (!learnerAnswer || state.grading[question.id]) return;

  const sentenceById = Object.fromEntries(
    state.package.article.sentences.map((sentence) => [sentence.id, sentence])
  );
  const evidenceSentences = question.evidence_sentence_ids
    .map((id) => sentenceById[id])
    .filter(Boolean);
  const requestId = createRequestId();
  state.grading[question.id] = true;
  delete state.gradeErrors[question.id];
  renderQuestion();
  try {
    const response = await fetch("/v1/grade", {
      method: "POST",
      headers: buildProviderHeaders(requestId),
      body: JSON.stringify({
        question,
        learner_answer: learnerAnswer,
        evidence_sentences: evidenceSentences,
        target_language: state.package.metadata.target_language,
        explanation_language: state.package.metadata.explanation_language,
      }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(parseError(body, response.status));
    state.grades[question.id] = body;
  } catch (caught) {
    state.gradeErrors[question.id] = caught.message || "AI 评分失败，请稍后重试。";
  } finally {
    state.grading[question.id] = false;
    if (state.package.questions[state.questionIndex]?.id === question.id) renderQuestion();
  }
}

function submitOrAdvance() {
  const questions = state.package.questions;
  const question = questions[state.questionIndex];
  if (!state.submitted[question.id]) {
    const selected = state.answers[question.id];
    const correct = question.evaluation_mode === "self_review"
      ? null
      : question.options?.length
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
    showToast(`练习完成：${scoreSummary()}`);
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
  const json = JSON.stringify(state.package, null, 2);
  const filename = `polyglot-quiz-${Date.now()}.json`;
  if (window.AndroidBridge?.saveJson) {
    window.AndroidBridge.saveJson(json, filename);
    showToast("JSON 已保存到下载目录");
    return;
  }
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
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
  $("#ai-grade-button").addEventListener("click", gradeOpenResponse);
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
