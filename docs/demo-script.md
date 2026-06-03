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

先点击“测试连接”：mock 模式应立即返回本地演示模型可用；部署设置访问口令后，可以展示登录模型配置区、填写外部模型信息、缺少 API key 时给出安全错误提示。运行诊断后，重点展示每段的建议标签、风险标记和差异视图，说明系统不是盲目改写，而是把疑似新增事实、术语变化和引用风险交给人工复核。

## 4:20-5:00 工程交付

展示 `.\scripts\verify.ps1`、`/healthz`、`Dockerfile` 和 `docker-compose.yml`。说明项目支持本地 5 分钟跑通，也能用 Docker 轻量部署到 Render 或 Railway；公网演示默认使用 mock 模型，真实模型需要访问口令保护，可通过网页配置或平台环境变量启用。

## 补充讲述点

- 评估指标：`python main.py eval-fixtures --json` 展示段落数、引注保留率、兜底数量、人工复核数量和工作流后端覆盖。
- 工作流轨迹：Web 右侧面板展示后端、条件审阅路线和实际执行节点，说明 LangGraph 已经参与风险路由。
- 条件审阅：出现术语变化、语义风险、兜底或仅分析结果时，工作流进入 `manual_review_required`；低风险结果进入 `quality_accepted`。
- 上线模型配置：已部署版本通过访问口令保护模型配置区，登录后可以填写厂商、服务地址、模型 ID 和 API key，再测试连接并调用外部模型。
