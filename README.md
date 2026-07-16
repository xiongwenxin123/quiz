# Polyglot Quiz

Grounded English, Japanese, and Spanish reading-quiz generation with local
graded vocabulary and grammar candidate selection.

The bundled learning profiles reduce free-form LLM target selection. See
[`docs/LEARNING_PROFILES.zh-CN.md`](docs/LEARNING_PROFILES.zh-CN.md) for data
sources, licenses, regeneration, and accuracy limitations.

面向英文、日语和西班牙语文章的可追溯出题服务。输入正文或公开 URL，系统先分析文章，再按语言专属规则生成题目，并用确定性规则检查题数、题型、答案结构和原文证据；失败时会要求模型完整返修。

这不是把一套英文题翻译成三种语言。共享管线负责抽取、结构化输出和质量控制，英文、日语、西班牙语配置分别负责难度体系、语法点、干扰项和书写规则。

## 已实现

- 正文输入和公开网页 URL 输入
- SSRF 基础防护、重定向逐跳检查、响应大小和超时限制
- Trafilatura 可选正文提取，未安装时使用内置 HTML 后备解析器
- 英文 CEFR、日语 JLPT、西班牙语 CEFR 配置
- 输入语言、题目语言与解析语言分离；当前题目语言与文章目标语言一致
- 文章分析与题目生成两阶段 LLM 调用
- JSON 数据契约、原文句子 ID、逐题证据片段
- 38 种题型，按基础理解、深层逻辑、语言词汇、写作输出、思辨拓展分类；默认仍为常用 9 题
- 确定性质量门槛与最多 3 次自动返修
- OpenAI-compatible JSON-mode 模型适配器
- 响应式前端工作台、CLI、FastAPI 接口、示例请求和单元测试

## 快速开始

Python 3.11 或更高版本：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[all]'
cp .env.example .env
```

设置环境变量（程序不会自动加载 `.env`）：

```bash
export QUIZ_LLM_API_KEY='...'
export QUIZ_LLM_MODEL='your-json-capable-model'
export QUIZ_LLM_BASE_URL='https://api.openai.com/v1'
```

CLI：

```bash
polyglot-quiz generate examples/english-request.json -o quiz-output.json
```

API：

```bash
uvicorn polyglot_quiz.api:app --host 127.0.0.1 --port 8000
curl -X POST http://127.0.0.1:8000/v1/quizzes \
  -H 'Content-Type: application/json' \
  --data @examples/japanese-request.json
```

浏览器打开 `http://127.0.0.1:8000/` 即可使用前端。没有模型密钥时，可启动内置演示服务：

```bash
uvicorn examples.demo_server:app --host 127.0.0.1 --port 8000
```

也可以点击页面右上角的模型设置按钮，临时填写 API Key、模型名和兼容接口地址。页面配置只保存在当前标签页内存中。

点击“保存为默认”会把配置写入项目根目录的 `.quiz-provider.json`。该文件权限为 `600` 且已被 Git 忽略，后续启动服务会自动使用，不需要环境变量。点击“仅本次使用”则不会写入文件。

本机或内网模型使用 `http://` 时，只需在页面明确勾选“允许明文 HTTP”。该模式仅适合绑定 `127.0.0.1` 的本地服务，不应直接暴露到公网。

历史 BBC 验证结果保存在 `bbc-quiz-output.json`：Trafilatura 提取 49 句、约 1285 词。当前默认蓝图为 9 种题型各 1 题；该历史文件仍保留当时 6 题配置的结果，质量分为 0.96。

测试：

```bash
make test
```

## 文档

- [完整设计与实施方案](docs/IMPLEMENTATION_GUIDE.zh-CN.md)
- [题型与语言规则](docs/QUESTION_DESIGN.zh-CN.md)
- [前端工作台](docs/FRONTEND.zh-CN.md)
- [接口、部署与运维](docs/OPERATIONS.zh-CN.md)

## 重要边界

CEFR/JLPT 标签是教学难度估计，不是官方认证。自动校验能证明引用存在、结构正确，但不能完全证明教学质量；正式发布题目仍应经过抽样人工审核和真实答题数据校准。网页抓取不会也不应绕过登录、付费墙、robots 限制或内容授权。
