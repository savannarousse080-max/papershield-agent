# PaperShield 演进实现计划

> **给执行型 Agent 的说明：** 按任务逐项执行本计划时，建议使用 `superpowers:subagent-driven-development`，也可以使用 `superpowers:executing-plans`。步骤使用复选框语法记录进度。

**目标：** 将 PaperShield 从“可部署演示”推进到更可信、可观察的学术写作审阅 Agent。

**架构：** 保持本地优先的 FastAPI/CLI 产品形态，同时通过可度量评估输出和 LangGraph 分支节点加深工作流。继续保留合规边界：质量审阅、语义保真、引注保护和人工复核，而不是承诺规避检测。

**技术栈：** Python unittest、FastAPI、原生 JavaScript/CSS、可选 LangGraph、确定性 mock 模型服务、PowerShell 验证脚本。

---

## 文件地图

- `agent/evaluation.py`：fixture 评估引擎，负责输出聚合质量、工作流和复核指标。
- `main.py`：结构化 fixture 评估输出的命令行入口。
- `fixtures/*.json`：确定性的产品证明样例。
- `agent/graph.py`：工作流图与分支节点。
- `agent/nodes/assemble.py`：带工作流可观测性的报告载荷。
- `web/static/index.html`：工作流轨迹面板结构。
- `web/static/app.js`：渲染并导出工作流轨迹。
- `web/static/styles.css`：工作流轨迹布局。
- `tests/test_cli.py`：命令行契约测试。
- `tests/test_web.py`：Web 载荷和静态界面测试。
- `tests/test_workflow.py`：工作流分支与拓扑测试。
- `README.md`、`docs/demo-script.md`、`PaperShield-Agent-PRD-v3.md`：产品叙事与演示脚本。

## 任务 1：可信评估报告

**文件：**
- 修改：`agent/evaluation.py`
- 修改：`main.py`
- 新增 fixture：`fixtures/law_semantic_addition_review.json`、`fixtures/economics_provider_failure.json`、`fixtures/general_analysis_only.json`
- 测试：`tests/test_cli.py`

- [ ] **步骤 1：编写失败的命令行/评估测试**

新增断言：`python main.py eval-fixtures --json` 返回 `metrics.total_paragraphs`、`metrics.average_citation_retention`、`metrics.review_required`、`metrics.fallback_count` 和 `metrics.workflow_backends`。

- [ ] **步骤 2：验证红灯**

运行：

```powershell
python -m unittest tests.test_cli.CliTests.test_eval_fixtures_json_outputs_structured_summary -v
```

预期：失败，因为此时还没有 `metrics`。

- [ ] **步骤 3：实现评估指标**

从每个评估后的 `AgentState` 收集段落数、兜底数量、复核建议数量、平均引注保留率和工作流后端数量。

- [ ] **步骤 4：新增 fixture**

加入语义复核、模型失败兜底和仅分析行为的确定性样例。

- [ ] **步骤 5：验证绿灯**

运行：

```powershell
python -m unittest tests.test_cli.CliTests.test_eval_fixtures_json_outputs_structured_summary -v
```

预期：通过。

## 任务 2：LangGraph 条件审阅分支

**文件：**
- 修改：`agent/graph.py`
- 测试：`tests/test_workflow.py`

- [ ] **步骤 1：编写失败的工作流分支测试**

断言拓扑包含 `review_gate`、`manual_review_required` 和 `quality_accepted`；断言存在语义风险的段落会经过 `manual_review_required`。

- [ ] **步骤 2：验证红灯**

运行：

```powershell
python -m unittest tests.test_workflow.WorkflowTests.test_workflow_routes_review_required_paragraphs -v
```

预期：失败，因为分支节点尚未存在。

- [ ] **步骤 3：实现分支节点**

新增 `review_gate`、`manual_review_required` 和 `quality_accepted`。LangGraph 路径从 `review_gate` 使用条件边；轻量本地回退路径用同样的顺序模拟路线判断。

- [ ] **步骤 4：保存路线元数据**

写入 `state.metrics["workflow_route"]`、`state.metrics["manual_review_required"]` 和完整节点轨迹。

- [ ] **步骤 5：验证绿灯**

运行：

```powershell
python -m unittest tests.test_workflow -v
```

预期：通过。

## 任务 3：产品界面与报告中的工作流轨迹

**文件：**
- 修改：`agent/nodes/assemble.py`
- 修改：`web/static/index.html`
- 修改：`web/static/app.js`
- 修改：`web/static/styles.css`
- 测试：`tests/test_web.py`、`tests/test_cli.py`

- [ ] **步骤 1：编写失败测试**

断言 API 载荷包含 `workflow.route`、`workflow.manual_review_required`，并断言 Web 静态文件包含 `workflow-trace`、`renderWorkflowTrace` 和本地化路线标签。

- [ ] **步骤 2：验证红灯**

运行：

```powershell
python -m unittest tests.test_web.WebAppTests.test_static_javascript_contains_workflow_trace tests.test_web.WebAppTests.test_optimize_text_with_mock_provider -v
```

预期：失败，因为界面轨迹尚未实现。

- [ ] **步骤 3：实现载荷与界面**

扩展 `workflow` 载荷，并渲染紧凑轨迹面板，展示后端、路线和节点。

- [ ] **步骤 4：验证绿灯**

再次运行 Web 相关测试。

## 任务 4：演示叙事更新

**文件：**
- 修改：`README.md`
- 修改：`docs/demo-script.md`
- 修改：`PaperShield-Agent-PRD-v3.md`
- 测试：`tests/test_deployment.py`

- [ ] **步骤 1：编写失败的文档测试**

断言文档提到评估指标、工作流轨迹和条件审阅路由。

- [ ] **步骤 2：验证红灯**

运行：

```powershell
python -m unittest tests.test_deployment.DeploymentReadinessTests.test_product_docs_are_aligned_with_demo_and_deployment_story -v
```

预期：文档更新前失败。

- [ ] **步骤 3：更新文档**

加入“可信评估 + 条件工作流 + 人工复核”的讲述逻辑和演示命令序列。

- [ ] **步骤 4：验证绿灯**

再次运行部署文档测试。

## 任务 5：完整验证

**文件：**
- 不修改生产代码。

- [ ] **步骤 1：运行定向测试**

运行：

```powershell
python -m unittest tests.test_cli tests.test_workflow tests.test_web.WebAppTests.test_optimize_text_with_mock_provider -v
```

- [ ] **步骤 2：运行完整验证**

运行：

```powershell
.\scripts\security-audit.ps1
.\scripts\verify.ps1
python -m pip check
```

- [ ] **步骤 3：运行冒烟检查**

运行：

```powershell
python main.py eval-fixtures --json
python main.py workflow-info --json
```

预期：所有命令退出码为 0，fixture 汇总包含指标，工作流拓扑包含条件审阅节点。

## 自查

- 规格覆盖：覆盖可信评估、LangGraph 分支路由、产品可观测性、文档和验证。
- 占位符扫描：没有未定义的未来需求。
- 类型一致性：工作流元数据始终通过 `AgentState.metrics` 和 `build_report_dict()` 传递。
