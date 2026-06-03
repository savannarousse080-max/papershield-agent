# PaperShield Evolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn PaperShield from a deployable demo into a more credible, observable academic-writing review agent.

**Architecture:** Keep the local-first FastAPI/CLI product shape, then deepen the workflow through measurable evaluation output and LangGraph branch nodes. Preserve the compliance boundary: quality review, semantic fidelity, citation protection, and human review instead of detector-evasion claims.

**Tech Stack:** Python unittest, FastAPI, plain JavaScript/CSS, optional LangGraph, deterministic mock provider, PowerShell verification scripts.

---

## File Map

- `agent/evaluation.py`: fixture evaluation engine; will report aggregate quality, workflow, and review metrics.
- `main.py`: CLI surface for structured fixture evaluation output.
- `fixtures/*.json`: deterministic product proof cases.
- `agent/graph.py`: workflow graph and branch nodes.
- `agent/nodes/assemble.py`: report payload for workflow observability.
- `web/static/index.html`: workflow trace panel shell.
- `web/static/app.js`: render workflow trace and export it.
- `web/static/styles.css`: workflow trace layout.
- `tests/test_cli.py`: CLI contract tests.
- `tests/test_web.py`: Web payload and static UI tests.
- `tests/test_workflow.py`: workflow branch and topology tests.
- `README.md`, `docs/demo-script.md`, `PaperShield-Agent-PRD-v3.md`: product story and demo script.

## Task 1: Evaluation Credibility Report

**Files:**
- Modify: `agent/evaluation.py`
- Modify: `main.py`
- Add fixtures: `fixtures/law_semantic_addition_review.json`, `fixtures/economics_provider_failure.json`, `fixtures/general_analysis_only.json`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI/evaluation tests**

Add assertions that `python main.py eval-fixtures --json` returns `metrics.total_paragraphs`, `metrics.average_citation_retention`, `metrics.review_required`, `metrics.fallback_count`, and `metrics.workflow_backends`.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_cli.CliTests.test_eval_fixtures_json_outputs_structured_summary -v`

Expected: FAIL because `metrics` does not exist.

- [ ] **Step 3: Implement evaluation metrics**

Collect paragraph count, fallback count, review recommendation count, average citation retention, and workflow backend counts from each evaluated `AgentState`.

- [ ] **Step 4: Add fixtures**

Add deterministic cases for semantic review, provider failure fallback, and analysis-only behavior.

- [ ] **Step 5: Verify GREEN**

Run: `python -m unittest tests.test_cli.CliTests.test_eval_fixtures_json_outputs_structured_summary -v`

Expected: PASS.

## Task 2: LangGraph Conditional Review Branch

**Files:**
- Modify: `agent/graph.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: Write failing workflow branch tests**

Assert topology includes `review_gate`, `manual_review_required`, and `quality_accepted`; assert a semantic-risk paragraph traces through `manual_review_required`.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_workflow.WorkflowTests.test_workflow_routes_review_required_paragraphs -v`

Expected: FAIL because branch nodes do not exist.

- [ ] **Step 3: Implement branch nodes**

Add `review_gate`, `manual_review_required`, and `quality_accepted`. For LangGraph use conditional edges from `review_gate`; for the simple fallback emulate the same route decision in order.

- [ ] **Step 4: Store route metadata**

Write `state.metrics["workflow_route"]`, `state.metrics["manual_review_required"]`, and full node trace.

- [ ] **Step 5: Verify GREEN**

Run: `python -m unittest tests.test_workflow -v`

Expected: PASS.

## Task 3: Workflow Trace in Product UI and Reports

**Files:**
- Modify: `agent/nodes/assemble.py`
- Modify: `web/static/index.html`
- Modify: `web/static/app.js`
- Modify: `web/static/styles.css`
- Test: `tests/test_web.py`, `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Assert API payload includes `workflow.route`, `workflow.manual_review_required`, and Web static files include `workflow-trace`, `renderWorkflowTrace`, and localized route labels.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_web.WebAppTests.test_static_javascript_contains_workflow_trace tests.test_web.WebAppTests.test_optimize_text_with_mock_provider -v`

Expected: FAIL because UI trace is missing.

- [ ] **Step 3: Implement payload and UI**

Extend `workflow` payload and render a compact trace panel showing backend, route, and nodes.

- [ ] **Step 4: Verify GREEN**

Run: `python -m unittest tests.test_web.WebAppTests.test_static_javascript_contains_workflow_trace tests.test_web.WebAppTests.test_optimize_text_with_mock_provider -v`

Expected: PASS.

## Task 4: Demo Story Update

**Files:**
- Modify: `README.md`
- Modify: `docs/demo-script.md`
- Modify: `PaperShield-Agent-PRD-v3.md`
- Test: `tests/test_deployment.py`

- [ ] **Step 1: Write failing docs test**

Assert docs mention evaluation metrics, workflow trace, and conditional review routing.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_deployment.DeploymentReadinessTests.test_product_docs_are_aligned_with_demo_and_deployment_story -v`

Expected: FAIL before docs are updated.

- [ ] **Step 3: Update docs**

Add a short "可信评估 + 条件工作流 + 人工复核" story and demo command sequence.

- [ ] **Step 4: Verify GREEN**

Run the deployment docs test again.

## Task 5: Full Verification

**Files:**
- No production edits.

- [ ] **Step 1: Run targeted tests**

Run:

```powershell
python -m unittest tests.test_cli tests.test_workflow tests.test_web.WebAppTests.test_optimize_text_with_mock_provider -v
```

- [ ] **Step 2: Run full verification**

Run:

```powershell
.\scripts\security-audit.ps1
.\scripts\verify.ps1
python -m pip check
```

- [ ] **Step 3: Run smoke checks**

Run:

```powershell
python main.py eval-fixtures --json
python main.py workflow-info --json
```

Expected: all commands exit 0, fixture summary includes metrics, workflow topology includes conditional review nodes.

## Self-Review

- Spec coverage: covers evaluation credibility, LangGraph branch routing, product observability, docs, and verification.
- Placeholder scan: no "TBD" or undefined future requirements.
- Type consistency: workflow metadata is always routed through `AgentState.metrics` and `build_report_dict()`.
