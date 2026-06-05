# PaperShield

PaperShield 是一个本地优先的学术文本质量审阅 Agent。它面向用户有权编辑的草稿，通过减少模板化连接词、保护引注、提示段落级风险并生成可人工复核的报告，提升文本的论证清晰度、表达自然度、术语一致性与引文可核查性。它不承诺绕过、规避或击败任何外部 AI 检测系统。

## 合规边界

- 仅用于你有权编辑、润色和提交的草稿。
- 所有事实、论点、术语、数据和引注都必须人工复核。
- 页面指标只是本地代理信号，不等同于任何检测器结果。
- 作品集演示版支持 `.txt`、基础 `.docx`、命令行流程和单用户 Web 审阅工作台。

## 5 分钟本地启动

PowerShell：

```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt
$env:PAPERSHIELD_LLM_PROVIDER="mock"
.\scripts\verify.ps1
.\scripts\start-web.ps1
```

cmd：

```cmd
python -m pip install -r requirements.txt -r requirements-dev.txt
set PAPERSHIELD_LLM_PROVIDER=mock
python main.py doctor
python -m unittest discover -s tests -v
python main.py workflow-info --json
python main.py eval-fixtures --json
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000` 使用工作台；打开 `http://127.0.0.1:8000/healthz` 验证服务状态。依赖与静态安全检查可在安装 `requirements-dev.txt` 后运行 `.\scripts\security-audit.ps1`。`setup-env.ps1` 只是本地参数化辅助脚本；真实密钥请放在当前 shell、`.env` 或 `setup-env.local.ps1` 中，这些文件已被 Git 忽略。

## Docker 演示

```bash
docker compose up --build
```

容器暴露 `8000` 端口，默认使用 `PAPERSHIELD_LLM_PROVIDER=mock`，无需模型密钥，适合公开作品集演示。

Render 或 Railway 部署要点：

- 使用本仓库内置 `Dockerfile` 构建。
- 暴露 `8000` 端口，Render 可通过平台提供的 `PORT` 环境变量启动。
- 使用 `/healthz` 作为健康检查路径。
- 公开演示可保持 `PAPERSHIELD_LLM_PROVIDER=mock`，不消耗任何模型额度。
- 若要给可信用户提供托管免费额度，设置 `PAPERSHIELD_PROVIDER_CONFIG_ENABLED=1`、`PAPERSHIELD_ADMIN_TOKEN` 和你的模型环境变量；用户登录访问密匙后会使用站点预设模型。可另设 `PAPERSHIELD_CONFIG_ADMIN_TOKEN`，只允许站长修改站点默认模型。
- 默认每个浏览器客户端可使用 `PAPERSHIELD_HOSTED_FREE_RUN_LIMIT=3` 次托管润色；用户也可以切换到“自备模型参数”，只用自己的 API key 和额度。
- Render 这类公网环境未设置 `PAPERSHIELD_ADMIN_TOKEN` 时，模型配置区会自动保持锁定。
- 不要把真实 API key 或访问口令提交到 GitHub。

免费 GitHub 同步部署流程见 `docs/deployment-free.md`。仓库已包含 `render.yaml`，用于 Render Blueprint/Web Service 部署，并开启从 `main` 分支自动重新部署。

## 命令行

```powershell
python main.py list-domains
python main.py doctor
python main.py optimize .\examples\demo_law.txt --domain law --output .\out --report-format all
python main.py optimize .\examples\demo_law.txt --domain law --output .\out --report-format all --analysis-only
python main.py test-paragraph "此外，数据安全问题需要完善[1]。" --domain law --json
python main.py workflow-info --json
python main.py eval-fixtures --json
```

`optimize` 会输出润色文本、文本/JSON/HTML 报告和人工复核清单。`--analysis-only` 只生成诊断，不改写正文，适合谨慎审阅 `.docx`。`workflow-info` 会返回当前编排后端和节点拓扑。

## Web 审阅工作台

Web 工作台支持粘贴文本、上传 `.txt` 和基础 `.docx`，主要能力包括：

- 法学、经济学、一般社科领域选择；
- 托管免费额度、自备模型参数与本地演示模型三种运行模式；
- 访问密匙保护下的托管额度，以及不消耗站点额度的自备模型参数；
- 仅分析模式；
- 逐段采纳润色或保留原文；
- 段落建议、语义保真风险、引注风险和行内差异；
- 后端、条件审阅路线和执行节点的工作流轨迹；
- 基于 `document_blocks` 的结构保留式最终稿合并；
- Markdown、HTML 和 Word 报告导出。

首次打开网站时会显示“用户须知”弹窗，确认后才进入工作台。若部署配置了 `PAPERSHIELD_ADMIN_TOKEN`，可信用户在“模型与运行环境”面板输入访问密匙后，可使用站点预设的托管模型额度；默认每个浏览器客户端 3 次，可通过 `PAPERSHIELD_HOSTED_FREE_RUN_LIMIT` 调整。用户也可以随时切换到“自备模型参数”，填写自己的服务地址、模型名和 API key；这类请求只在本次调用使用用户参数，不消耗站点托管额度。

## 架构

实现刻意保持轻量，便于验证和部署：

1. 解析 `.txt` 或基础 `.docx`，分段、保护引注，并保留标题、图表、表格和参考文献。
2. 执行第一层句式自然化，减少模板化表达。
3. 执行第二层领域化学术措辞增强。
4. 计算组合本地诊断指标：困惑度代理、句长变化、模板词减少率和引注保留率。
5. 生成段落级风险标记、语义保真提示、采纳建议和人工复核清单。
6. 通过条件审阅门禁分流：低风险草稿进入 `quality_accepted`，高风险草稿进入 `manual_review_required`。
7. 低质量段落最多重试一次，仍不达标时安全保留原文。
8. 组装最终文本和文本/JSON/HTML/Word 报告。
9. 通过 FastAPI 将同一套流程提供给本地、Docker 和线上演示。

安装 `requirements-optional.txt` 可启用 LangGraph 编排。安装后，`optimize_text()` 与 `build_graph()` 会执行条件 `StateGraph`；未安装时会自动回退到轻量本地图。结构化命令行和 Web 报告都会包含 `workflow.backend`、`workflow.route`、`workflow.nodes` 与工作流轨迹，便于观察 Agent 决策路径。`eval-fixtures --json` 会汇总质量指标、审阅路由数量、兜底数量、引注保留率和工作流后端覆盖情况。可选 ML 评分依赖放在 `requirements-ml.txt`，快速演示路径不需要安装。

## 模型配置

常用环境变量：

- `PAPERSHIELD_LLM_PROVIDER=mock|openai|anthropic`
- `PAPERSHIELD_PROMPT_PROFILE=default|research_writing_zh_word_v1`
- `PAPERSHIELD_LLM_MODEL`
- `PAPERSHIELD_LLM_BASE_URL`
- `PAPERSHIELD_LLM_TIMEOUT`
- `PAPERSHIELD_LLM_MAX_RETRIES`
- `PAPERSHIELD_API_KEY`、`OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`
- `PAPERSHIELD_PROVIDER_CONFIG_ENABLED=0|1`
- `PAPERSHIELD_ADMIN_TOKEN`，可信用户访问密匙，用于登录托管免费额度
- `PAPERSHIELD_CONFIG_ADMIN_TOKEN`，可选站点配置管理员密匙；设置后，只有它能保存站点默认模型配置，`PAPERSHIELD_ADMIN_TOKEN` 只用于用户托管额度
- `PAPERSHIELD_REQUIRE_ADMIN_TOKEN_FOR_PROVIDER_USE=0|1`，私有部署可设为 `0`，让用户免登录直接运行已配置的外部模型
- `PAPERSHIELD_HOSTED_FREE_RUN_LIMIT`，可信用户每个浏览器客户端可使用的托管免费润色次数，默认 `3`
- `PAPERSHIELD_MAX_UPLOAD_BYTES`、`PAPERSHIELD_MAX_TEXT_CHARS`、`PAPERSHIELD_MAX_PARAGRAPHS`
- `PAPERSHIELD_OPTIMIZE_RATE_LIMIT_PER_MINUTE`、`PAPERSHIELD_PROVIDER_RATE_LIMIT_PER_MINUTE`

公开演示可以保持 `mock`。真实模型适合私有运行，或在设置访问密匙后作为托管免费额度开放给可信用户。自备模型参数模式会使用用户本次填写的 key 和模型配置。模型服务地址必须使用 HTTPS，并会阻止 localhost、私有地址、链路本地地址、多播地址和云元数据地址。

提示词方案：

- `default`：PaperShield 内置稳妥方案。
- `research_writing_zh_word_v1`：PaperShield 自有中文研究写作方案，强调不信任草稿内容、保护引注占位符、输出 Word 兼容纯文本，并避免外部检测器承诺。

模型辅助接口：

- `GET /api/provider/status`：返回模型服务、模型名、提示词方案、超时、重试和是否存在 API key，不返回密钥。
- `GET /api/provider/presets`：返回常见模型服务商预设。
- `POST /api/provider/session`：验证访问密匙，成功后前端解锁托管免费额度。
- `POST /api/provider/config`：保存非密钥字段，并把 API key 暂存于当前后端进程内。
- `POST /api/provider/check`：测试选定模型模式；`mock` 本地免费，`hosted` 使用站点托管模型，`user` 使用本次提交的自备参数。
- `GET /api/runtime/policy`：返回上传、文本、段落限制和模型配置策略。
