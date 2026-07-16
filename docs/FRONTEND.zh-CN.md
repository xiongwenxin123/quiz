# 前端工作台

## 1. 实现方式

前端采用原生 HTML、CSS 和 JavaScript，作为 `polyglot_quiz` Python 包的静态资源发布。它不需要 Node.js、打包器或独立开发服务器，和 FastAPI 使用同一个域名：

```text
GET  /                    前端入口
GET  /assets/styles.css   样式
GET  /assets/app.js       交互
GET  /health              服务状态
GET  /v1/config           三语与题型配置
POST /v1/quizzes          生成练习
```

对应文件：

- `src/polyglot_quiz/web/index.html`
- `src/polyglot_quiz/web/styles.css`
- `src/polyglot_quiz/web/app.js`
- `src/polyglot_quiz/api.py`

`pyproject.toml` 已将 `web/*` 声明为 package data，因此 wheel 和可编辑安装都会包含页面资源。

## 2. 功能

### 2.1 出题设置

- 正文与 URL 两种来源切换；
- 正文字符计数和最小 80 字符校验；
- 英文、日语、西班牙语切换；
- CEFR/JLPT 等级自动联动；
- 中文、英文、日语、西语解析语言；
- 西语地区变体；
- 日语假名开关；
- 九类题型独立步进器和总题数统计；
- 内置三语示例文章。

页面右上角的模型设置支持 OpenAI、Qwen/DashScope、DeepSeek 和自定义 OpenAI-compatible HTTP(S) 接口。配置成功后，这次请求携带的模型设置会覆盖演示提供器或服务器环境配置。HTTP 地址只需在页面明确勾选风险确认。

- `仅本次使用`：密钥只留在当前标签页内存，刷新后清除；
- `保存为默认`：写入本机 `.quiz-provider.json`，后续启动自动使用；
- `清除默认`：删除本机配置文件，不影响服务器环境变量；
- 查询接口只返回模型名、Base URL 和配置来源，不返回密钥。

### 2.2 生成状态

提交后显示阶段化加载文案，生成按钮进入禁用状态，防止重复提交。后端 422、502 和字段校验错误会显示在表单下方，并保留当前配置和文章。

### 2.3 答题状态

- 单题逐步作答；
- 支持选择题和简答题；
- 未选答案时禁止提交；
- 提交后锁定答案并标记正误；
- 显示指定语言的解析与原文证据；
- 记录当前正确数和已答题数；
- 可以返回已答题目查看解析；
- 完成后展示成绩提示。

简答题目前使用归一化后的完全匹配：忽略首尾空白、大小写和末尾常用标点。需要更宽松的语义判分时，应新增后端判分接口，而不是在浏览器中嵌入答案判断模型。

### 2.4 结果视图

- `练习`：题目、选项、进度、反馈；
- `文章`：按证据句 ID 显示清洗后的原文；
- `词汇`：目标词、词元/读音、语境义和估计等级；
- `导出 JSON`：下载完整 `QuizPackage`；
- `关闭练习`：清空结果但保留左侧输入。

## 3. 启动

真实模型模式：

```bash
cd /Users/arthurbear/Desktop/quiz
source .venv/bin/activate
export QUIZ_LLM_API_KEY='...'
export QUIZ_LLM_MODEL='...'
uvicorn polyglot_quiz.api:app --host 127.0.0.1 --port 8000
```

无密钥演示模式：

```bash
cd /Users/arthurbear/Desktop/quiz
source .venv/bin/activate
uvicorn examples.demo_server:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000/`。演示模式会在页头标明“演示模式”；保持英文 B1、默认 9 种题型各 1 题，点击“载入演示文章”后生成。演示服务会明确拒绝其他文章，避免固定演示题与自定义正文产生错误的证据引用。

## 4. 响应式设计

- 大于 860px：左侧固定宽度配置区，右侧结果工作区；
- 小于等于 860px：配置区与结果区上下排列；
- 小于等于 540px：字段改为单列，结果操作区和词汇行重新排版；
- 固定格式控件使用明确网格和最小高度，动态文本不会改变步进器和选项布局；
- 支持 `prefers-reduced-motion`；
- 390px 实测页面宽度与滚动宽度一致，不产生横向滚动。

## 5. 安全

- 所有 API 返回文本在插入 HTML 前经过实体转义；
- 文章、题目和解析不会以 `innerHTML` 原样执行；
- 前端不会持久化模型 API 密钥；
- 页面临时配置的 API 密钥只存在于当前标签页 JavaScript 内存和生成请求头中，不写入 Cookie、`localStorage` 或 `sessionStorage`；刷新页面后自动清除；
- 后端不记录模型配置请求头；HTTPS 地址必须解析到公网；HTTP 只在用户明确确认后启用，因此服务应绑定 `127.0.0.1`，不应直接暴露到公网；
- HTTP 无法保护后端到模型服务之间的 API Key 和内容，只应用于可信本机或受控内网；
- 服务器环境变量仍适合长期部署，页面配置适合本地使用和临时测试；
- JSON 导出使用浏览器内存 Blob，不上传到第三方；
- 当前页面与 API 同源，不开放宽泛 CORS。

## 6. 测试

自动测试验证：

- 页面和 CSS/JS 静态资源可访问；
- 配置接口返回三种语言；
- 前端脚本调用正确的健康检查和生成接口；
- 演示请求通过完整生成、质量检查和 API 序列化管线。

浏览器实测覆盖桌面与 390x844 移动端，验证示例载入、生成、选择答案、提交、正确反馈、证据解析和词汇标签页。浏览器控制台无 error 或 warning。

运行：

```bash
source .venv/bin/activate
make compile
make test
```

## 7. 后续扩展

前端保持无构建依赖适合当前 MVP。进入多人协作、账户系统或复杂内容编辑后，可以迁移到组件框架，但应保持 `/v1/quizzes` 和 `QuizPackage` 契约不变。优先扩展顺序：

1. 题目人工编辑与发布状态；
2. 登录、历史记录和练习恢复；
3. 证据句点击高亮；
4. 音频播放与听力题；
5. 学习者掌握度和间隔复习；
6. 管理端质量审核量表。
