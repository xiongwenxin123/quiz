# 接口、部署与运维

## 1. 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[all]'
export QUIZ_LLM_API_KEY='...'
export QUIZ_LLM_MODEL='...'
export QUIZ_LLM_BASE_URL='https://your-provider.example/v1'
```

没有网页输入需求时可以只安装基础包；Trafilatura 属于 `extract` extra，FastAPI/Uvicorn 属于 `api` extra。

## 2. CLI

查看请求 JSON Schema：

```bash
polyglot-quiz schema
```

生成：

```bash
polyglot-quiz generate examples/spanish-request.json -o quiz-output.json
```

成功退出码为 0。请求无效、模型调用失败或最终质量校验失败时退出码为 1，错误写入 stderr，不生成看似成功的降级结果。

## 3. HTTP API

启动：

```bash
uvicorn polyglot_quiz.api:app --host 127.0.0.1 --port 8000
```

浏览器访问 `http://127.0.0.1:8000/` 使用前端工作台。页面与 API 同源，因此本地运行不需要额外配置 CORS。

没有模型密钥时，可以用固定英文题目检查完整前端流程：

```bash
uvicorn examples.demo_server:app --host 127.0.0.1 --port 8000
```

演示服务只支持默认英文示例和默认 9 种题型各 1 题的蓝图，不应用于生产。

前端右上角可以临时配置 API Key、模型名和 OpenAI-compatible Base URL。配置通过 `X-Quiz-LLM-*` 同源请求头仅用于当前生成请求，不持久化。面向公网部署时，建议关闭或在网关限制这一能力，并统一使用服务端密钥和供应商白名单。

如果可信本机/内网模型只有 HTTP 接口，直接在前端填写 `http://.../v1` 并勾选“允许明文 HTTP”。不需要设置环境变量。该开关会让 API Key 和文章在后端到模型服务这一段以明文传输，因此服务应使用 `--host 127.0.0.1`，不适合公网部署。

“兼容模式”控制响应协议：

- `自动识别`：模型名以 `qwen` 开头时使用 SSE 流式响应，其他模型使用标准 OpenAI 非流式响应；
- `标准 OpenAI 非流式`：读取 `choices[0].message.content`，并兼容部分服务的 `reasoning` 字段；
- `Qwen SSE 流式`：聚合 `choices[0].delta.content`、`delta.reasoning` 或 `delta.reasoning_content`。

部分自建 Qwen 网关虽然使用 `/v1/chat/completions` 和 OpenAI 请求体，但非流式响应可能只有 `{"role":"assistant"}`，实际文本只在 SSE 分片中返回。这类服务应使用“自动识别”或“Qwen SSE 流式”。

### GET /health

只证明进程可响应，不会调用模型：

```json
{"status": "ok"}
```

### POST /v1/quizzes

请求体为 `QuizRequest`，示例见 `examples/`。成功返回 `QuizPackage`。

错误约定：

| 状态码 | 场景 |
| --- | --- |
| 422 | 请求字段无效、语言不匹配或生成题最终未通过质量门槛 |
| 502 | 上游 LLM 网络、鉴权、返回格式或 Schema 错误 |

FastAPI 自动提供 `/docs` 和 `/openapi.json`。

## 4. Docker

```bash
docker build -t polyglot-quiz:0.1 .
docker run --rm -p 8000:8000 \
  -e QUIZ_LLM_API_KEY \
  -e QUIZ_LLM_MODEL \
  -e QUIZ_LLM_BASE_URL \
  polyglot-quiz:0.1
```

镜像以非 root 用户运行。生产环境应进一步固定依赖哈希、只读根文件系统、CPU/内存限制和出站网络策略。

## 5. 安全清单

### 5.1 URL 抓取

- 在网络层拒绝私网、环回、链路本地和云元数据地址；
- 使用独立抓取身份，不携带用户 Cookie；
- 限制响应体、重定向、连接时间和总时间；
- 不允许任意 Content-Type；
- 不把付费墙失败当成空文章继续生成；
- 保存内容来源、抓取时间、授权和删除策略。

### 5.2 提示词注入

文章是非可信数据。当前提示词使用 `<article>` 边界并明确禁止执行其中指令。生产还应：

- 模型调用不配置浏览器、数据库或代码执行工具；
- 生成服务密钥只拥有调用模型的最低权限；
- 不把用户文章拼入 system 指令；
- 记录模型输入摘要与输出，但对个人信息做脱敏；
- 对异常长指令样式文本和输出偏离进行监控。

### 5.3 API

- 增加身份认证、租户限额和每 IP/用户速率限制；
- `source_text` 已限制 100000 字符，网关还应限制请求体；
- API 密钥只从密钥管理系统注入，不写进镜像或日志；
- 面向儿童或学校使用时，单独处理隐私、内容安全和数据保留要求。

## 6. 可观测性

每次任务建议记录这些结构化字段：

- request/job ID、租户 ID；
- 语言、等级、题型蓝图、正文哈希和字符数；
- 模型、提示词版本、各阶段 token 和耗时；
- 生成尝试次数、错误代码、质量分；
- 抓取方法和最终 URL 域名（避免完整查询参数进入日志）；
- 发布、人工修改和删除状态。

关键指标：

- 端到端成功率；
- 首次质量通过率和返修后通过率；
- Schema 失败率、证据失败率、语言不匹配率；
- P50/P95 延迟；
- 每篇文章和每道合格题的模型成本；
- 各语言人工拒绝率。

模型供应商错误只写入后端日志。日志包含请求 ID、模型、Base URL、上游状态码和截断后的响应摘要，不包含 API Key。前端只显示安全的错误类别和请求 ID；上游 429 会映射为 503，并提示限流或额度不足。

### 结构化事件

所有业务日志以 `quiz_event` 开头，后跟单行 JSON。一次请求中的事件共享 `request_id`：

| 事件 | 记录内容 |
| --- | --- |
| `request_received` | 来源类型、语言、等级、题数 |
| `provider_selected` | 配置来源、模型、Base URL |
| `pipeline_started` | 题型蓝图 |
| `extraction_started/completed` | 提取方式、字符、句子、词数、耗时 |
| `url_download_retry` | 下载重试次数和网络错误类型 |
| `learning_targets_selected` | 本地分级词汇/语法候选数量、来源和耗时 |
| `analysis_started/completed` | 主题、词汇/语法目标数量、耗时 |
| `analysis_targets_grounded` | 被本地资料拒绝或纠正的模型目标数量 |
| `llm_request_started` | 模型、端点、Schema、提示词字符数、传输模式和尝试次数 |
| `llm_response_received` | HTTP 状态、字节数、耗时 |
| `llm_stream_completed` | SSE 状态、分片数、字节数、token 用量和结束原因 |
| `llm_output_selected` | 使用 `content`、`reasoning`、`reasoning_content` 或相应 `delta` 字段 |
| `llm_retry_scheduled` | 空响应、Schema 错误、429、5xx 或连接中断后的重试安排 |
| `llm_response_validated` | Schema 校验和总耗时 |
| `generation_started/completed` | 候选题数量和耗时 |
| `evidence_quotes_grounded` | 安全替换为原句的题号、句号和重合度 |
| `quality_checked` | 尝试次数、分数、错误/警告代码 |
| `repair_started` | 自动返修原因和下一次尝试 |
| `answer_options_shuffled` | 重排后正确答案在 A-D 或 A-B 的数量分布 |
| `pipeline_completed` | 题数、质量分、总耗时 |
| `request_completed` | HTTP 200、总耗时 |

日志不会写入 API Key、完整正文、完整提示词或完整模型响应。异常响应只保留最多 1000 字符的摘要，并主动替换可能出现的密钥。

### 本机默认模型

前端保存的默认模型位于 `.quiz-provider.json`，权限为 `0600`，并已加入 `.gitignore`。优先级为：请求临时配置 > 注入提供器 > 环境变量 > 本机默认文件。接口：

```text
GET    /v1/provider-settings  查询脱敏状态
PUT    /v1/provider-settings  保存默认配置
DELETE /v1/provider-settings  清除默认配置
```

### 真实生成进度

前端在 `POST /v1/quizzes` 中发送随机的 `X-Quiz-Request-ID`，并轮询
`GET /v1/progress/{request_id}`。进度由 Pipeline 在正文提取、本地分级匹配、
模型分析、题目生成、证据核对、质量检查和返修边界主动更新；前端不再定时轮换
猜测文案。状态只包含阶段、提示、粗粒度百分比和完成标记，不包含文章、Prompt
或模型响应。

进度状态保存在当前 Python 进程内，15 分钟后自动清理。本地单进程 Uvicorn 可直接
使用；多 worker 或多实例部署应将 `ProgressStore` 替换为 Redis 等共享存储，否则
轮询可能被路由到另一个进程而返回 404。

### 答案位置重排

题目通过质量检查后，后端才会重排选择题选项。四选一题按随机化的 A-D
循环分配正确答案位置，判断题按 A-B 循环分配；每题的干扰项再独立随机排列，
最后统一重写选项 ID 和 `correct_option_id`。因此连续四道四选一题的正确位置会
覆盖 A、B、C、D 各一次，避免继承模型偏爱 A/B 的位置分布。

Prompt 禁止解析引用选项字母；兼容已有模型输出时，后处理还会同步重映射
`Option A`、`选项A`、`選択肢A`、`opción A` 和括号形式的引用。

不要提交或复制 `.quiz-provider.json`。备份项目时应把它作为密钥处理。

### BBC 实际验证

`https://www.bbc.com/news/articles/crele3r8j19o` 已完成真实端到端验证：

- Trafilatura：7902 字符、49 句、1285 词；
- 模型：`qwen3.6-35b`；
- 输出：英文 B2、中文解析、6 题；
- 结果：HTTP 200、质量分 0.96、一次生成通过；
- 产物：项目根目录 `bbc-quiz-output.json`；
- BBC 下载出现一次不完整响应时，自动重试后成功。

告警不要只看 HTTP 5xx。若接口仍返回成功但返修率或人工拒绝率突然上升，通常意味着模型版本、网页结构或提示词发生了质量回归。

## 7. 重试与幂等

- HTTP 429、可恢复 5xx 和连接中断可以指数退避重试；
- Schema 不匹配属于内容返修，不应与网络重试混为一谈；
- 客户端提交幂等键，服务端保存相同请求的 job ID；
- 缓存键包含正文哈希、请求配置、模型版本、提示词版本；
- 不无限返修，当前上限为 3 次，避免成本失控。

## 8. 测试与发布门槛

本地测试：

```bash
make compile
make test
```

当前自动测试覆盖请求约束、日语分句、私网 URL 阻止、证据校验、合格题通过和失败题自动返修。生产 CI 还应加入：

- 三语真实网页抽取回归集；
- 供应商 API 契约测试；
- 固定金标集的离线模型评测；
- 依赖与容器漏洞扫描；
- 负载、超时和限流测试；
- 每次提示词或模型变更的质量差异报告。

发布模型/提示词时使用影子流量或小比例灰度。质量指标未达到旧版本时自动回滚，不以“新模型更大”作为升级依据。

## 9. 故障处理

### 模型返回非 JSON

确认供应商支持 JSON mode、模型名正确、兼容端点行为一致。失败会作为 502 返回，不会用字符串正则拼装残缺对象。

### 质量返修后仍失败

检查错误代码。如果主要是 `invented_quote`，模型可能在改写原文；如果是 `type_count`，降低一次请求题量或更换结构化输出能力更强的模型。不要直接关闭校验。

### URL 提取正文过短

网页可能依赖客户端渲染、需要登录或正文结构不适合静态抽取。由有授权的上游浏览器/抓取服务提供清洗后的 `source_text`，不要在生成服务里加入隐蔽绕过逻辑。

### 难度不稳定

先看文章本身是否远高于目标等级。题目可以降低问题复杂度，但不能让高难原文变成真正的初级阅读。产品应在生成前提示文章难度偏差，后续可加入受控简化模块，并把简化文本与原文分版本保存。
