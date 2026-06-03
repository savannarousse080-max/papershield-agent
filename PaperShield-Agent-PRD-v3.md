# PaperShield Agent - 演示可用版产品需求文档 PRD v3.2

> 版本: v3.2 | 2026-06-01  
> 定位: 个人学习项目 · AI Agent 技术实践 · AIPM 求职作品集  
> 形态: 本地 CLI + 单用户 Web Demo + 轻量 Docker 部署  

## 一、产品定义

PaperShield 是一个**学术文本质量提升与 AI 风格风险诊断 Agent**。

它面向用户自有草稿，帮助用户降低模板化表达、提升句式变化、保护引注与术语，并生成可人工复核的诊断报告。产品不承诺任何外部检测系统结果，也不面向欺骗性提交场景。

本版本目标从早期 CLI MVP 升级为**演示可用版**：既能在作品集里清楚展示产品判断，也能在本地或 Docker 环境中快速上线。

## 二、当前支持能力

- 本地 CLI：领域列表、健康诊断、单段测试、整篇优化、fixture 回归。
- 输入格式：`.txt` 与基础 `.docx`，支持表格单元格文本读取和写回。
- Web Demo：粘贴文本、上传 `.txt/.docx`、逐段审阅、采纳/保留、最终稿合并、Markdown/HTML 导出。
- 模型模式：无密钥 mock provider；OpenAI 兼容 provider；Anthropic provider。
- Provider 体验：Web 可查看 provider 配置状态，并在运行前测试 mock/env 连接。
- 报告格式：文本、JSON、HTML、人工复核清单。
- 快速上线：PowerShell 验证脚本、Web 启动脚本、Dockerfile、docker-compose、`/healthz`。

## 三、核心目标

1. **表达质量提升**：减少“此外、因此、综上所述”等模板连接词，增强句式长短变化。
2. **学术风格增强**：根据 law、economics、general 三类领域配置引入更合适的学术表达。
3. **结构保护**：保护 `[1]`、`[1][2]`、`(张三, 2021)`、上标脚注、标题、图表和参考文献块。
4. **可复核诊断**：报告包含困惑度代理、句长变异、模板词减少、引注保留、段落状态、风险标记。
5. **语义保真**：标记疑似新增事实、术语变化、未变化输出，并给出段落级采纳建议。
6. **稳定容错**：单段处理失败时保留原文，不中断整篇处理。
7. **快速上线**：作品集检查者能在 5 分钟内完成本地验证，也能通过 Docker 启动 Web Demo。

## 四、工作流设计

```text
输入 .txt/.docx
  -> Parse：分段、保护引注、保留标题/图表/参考文献
  -> Layer 1：句式自然化，减少模板表达
  -> Layer 2：领域学术表达增强，保护术语与引注
  -> Score：组合指标评分
  -> Route：质量不足最多重试一次，失败则原文兜底
  -> Fidelity：语义保真风险、差异片段、采纳建议
  -> Review：风险标记与人工复核清单
  -> Assemble：还原结构，输出最终稿与报告
```

Web JSON 报告保留 `paragraphs/final_text/report`，并新增 `document_blocks`，用于前端按原文结构合并标题、正文、图表和参考文献。

## 五、外部接口

### CLI

```powershell
python main.py list-domains
python main.py doctor
python main.py optimize .\examples\demo_law.txt --domain law --output .\out --report-format all
python main.py optimize .\examples\demo_law.txt --domain law --output .\out --report-format all --analysis-only
python main.py eval-fixtures --json
```

### Web API

- `GET /healthz`：返回 `status`, `version`, `provider`, `dependencies`, `compliance_mode`。
- `GET /api/provider/status`：返回 provider、model、是否配置 API key、超时与重试设置，不返回密钥。
- `POST /api/provider/check`：测试 mock 或 env provider；mock 不需要密钥，env 会使用环境变量配置。
- `POST /api/optimize`：支持 `text`, `domain`, `provider_mode`, `analysis_only`, `file`。

### LLM Provider

- `PAPERSHIELD_LLM_PROVIDER=mock`：本地演示和测试，无需密钥。
- `PAPERSHIELD_LLM_PROVIDER=openai`：OpenAI 兼容接口。
- `PAPERSHIELD_LLM_PROVIDER=anthropic`：Anthropic Messages API。

公网 Demo 默认使用 `mock`，真实 provider 只用于私有部署或本地验证。

## 六、评估指标

| 指标 | 含义 | 验收目标 |
| --- | --- | --- |
| 困惑度代理变化 | 本地中文兼容语言多样性代理指标 | 仅作参考，不等同外部系统 |
| 句长变异 | 句子长度分布是否更自然 | 相比原文不下降或可解释 |
| 模板词减少率 | 模板连接词减少比例 | 样本目标 >= 75% |
| 引注保留率 | 引注数量是否完整保留 | 100% |
| 语义保真提示 | 疑似新增事实、术语变化、未变化输出 | 必须进入人工复核清单 |
| 段落状态 | accepted / below_threshold / fallback / analysis_only | 失败段落不影响全局 |

## 七、快速上线要求

- `scripts/verify.ps1` 一键运行 doctor、单元测试和 fixture。
- `scripts/start-web.ps1` 一键启动 FastAPI Web Demo。
- `Dockerfile` 和 `docker-compose.yml` 能以 mock provider 启动 8000 端口。
- `/healthz` 可作为 Render/Railway 健康检查。
- 错误响应不得暴露密钥或内部堆栈。

## 八、验收标准

1. README、PRD、CLI/Web 输出必须明确合规边界。
2. `python -m unittest discover -s tests -v` 全部通过。
3. `python main.py eval-fixtures --json` 内置样例全部通过。
4. `.txt/.docx` 输入均可生成最终稿、结构化报告和复核清单。
5. Web 的最终稿合并依赖 `document_blocks`，不通过字符串替换猜测段落。
6. Docker 镜像能启动 Web Demo，`/healthz` 返回 `status=ok`。

## 九、后续版本

- v1.5：更强语义保真检查与差异视图。
- v1.6：更完整的 `.docx` 格式保真与批注导出。
- v1.7：可选 LangGraph 编排与可观测性事件。
- v1.8：可选 ML scorer 与批量评估面板。

## v1.9 Evolution Focus

- Evaluation metrics: fixture regression now summarizes paragraph count, citation retention, fallback count, manual review count, and workflow backend coverage.
- Conditional review: LangGraph adds a `review_gate` route. Risky drafts enter `manual_review_required`; low-risk drafts enter `quality_accepted`.
- Workflow trace: CLI/Web reports expose backend, route, and executed nodes so reviewers can inspect the Agent decision path.

## 十、作品集讲述重点

PaperShield 展示的是 AI 产品经理对“能力、边界、风险、可验证性、上线速度”的平衡：

- 不把外部黑盒检测结果当作目标，而是构建本地可解释指标。
- 不绕开学术诚信问题，而是把人工复核、引注保护和使用边界写进产品设计。
- 不追求复杂生产系统，而是用单体 FastAPI、脚本和 Docker 快速形成可演示、可验证、可部署的闭环。
