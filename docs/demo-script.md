# PaperShield 5 分钟演示脚本

## 0:00-0:45 问题与边界

PaperShield 解决的是学术草稿的表达质量诊断与审阅协作问题：减少模板化表达、保护引注和术语、输出可复核报告。它不承诺绕过任何外部检测器，指标只作为本地代理信号，最终稿必须人工复核。

## 0:45-2:00 Agent 工作流

展示 `python main.py doctor` 与 `python main.py eval-fixtures --json`。说明工作流包括解析、引注保护、两层改写、组合指标、失败兜底、报告组装。重点讲清楚：失败段落保留原文，标题、图表、参考文献不进入改写。

## 2:00-3:15 CLI 与报告

运行：

```powershell
$env:PAPERSHIELD_LLM_PROVIDER="mock"
python main.py optimize .\examples\demo_law.txt --domain law --output .\out --report-format all
```

打开 `out/demo_law_report.html` 或 `out/demo_law_report.json`，展示逐段状态、风险标记、引注保留率和人工复核清单。

## 3:15-4:20 Web 审阅台

运行：

```powershell
.\scripts\start-web.ps1
```

打开 `http://127.0.0.1:8000`，粘贴示例文本或上传 `.txt/.docx`。展示采纳润色、保留原文、最终稿合并、导出 Markdown/HTML，以及“仅分析”模式。

先点击“测试连接”：mock 模式应立即返回本地演示模型可用；切换到 env 模式时，可以展示缺少 API key 时的安全错误提示。运行诊断后，重点展示每段的建议标签、风险标记和差异视图，说明系统不是盲目改写，而是把疑似新增事实、术语变化和引用风险交给人工复核。

## 4:20-5:00 工程交付

展示 `.\scripts\verify.ps1`、`/healthz`、`Dockerfile` 和 `docker-compose.yml`。说明项目支持本地 5 分钟跑通，也能用 Docker 轻量部署到 Render 或 Railway；公网 Demo 默认使用 mock provider，真实模型只通过环境变量启用。

## 补充讲述点

- Evaluation metrics: `python main.py eval-fixtures --json` 展示段落数、引注保留、fallback 数、人工复核数量和 workflow backend 覆盖。
- Workflow trace: Web 右侧面板展示 backend、conditional review route 和实际执行节点，说明 LangGraph 已经参与风险路由。
- Conditional review: 有术语变化、语义风险、fallback 或仅分析结果时，工作流进入 `manual_review_required`；低风险结果进入 `quality_accepted`。
