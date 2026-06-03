const form = document.querySelector("#optimize-form");
const providerConfigForm = document.querySelector("#provider-config-form");
const statusBox = document.querySelector("#status");
const finalText = document.querySelector("#final-text");
const metricsBox = document.querySelector("#metrics");
const reviewItems = document.querySelector("#review-items");
const reviewWorkbench = document.querySelector("#review-workbench");
const workflowTrace = document.querySelector("#workflow-trace");
const copyFinalButton = document.querySelector("#copy-final");
const downloadMarkdownButton = document.querySelector("#download-markdown");
const downloadHtmlButton = document.querySelector("#download-html");
const downloadWordButton = document.querySelector("#download-word");
const checkProviderButton = document.querySelector("#check-provider");
const providerStatus = document.querySelector("#provider-status");
const providerModeSetting = document.querySelector("#provider-mode-setting");
const providerModeInput = document.querySelector("#provider-mode-input");
const providerPresetSelect = document.querySelector("#provider-preset");
const providerProviderSelect = document.querySelector("#provider-provider");
const providerBaseUrlInput = document.querySelector("#provider-base-url");
const providerModelInput = document.querySelector("#provider-model");
const providerApiKeyInput = document.querySelector("#provider-api-key");
const providerProfileSelect = document.querySelector("#provider-profile");
const providerTimeoutInput = document.querySelector("#provider-timeout");
const providerMaxRetriesInput = document.querySelector("#provider-max-retries");
const clearProviderKeyButton = document.querySelector("#clear-provider-key");
const providerSummary = document.querySelector("#provider-summary");
const providerAlert = document.querySelector("#provider-alert");
const requestEstimate = document.querySelector("#request-estimate");
const textInput = document.querySelector("#text-input");
const fileInput = document.querySelector('input[name="file"]');
const fileName = document.querySelector("#file-name");
const runButton = document.querySelector("#run-button");
const resultSummary = document.querySelector("#result-summary");
const analysisOnlyInput = document.querySelector('input[name="analysis_only"]');
const artifactTabs = document.querySelectorAll("[data-artifact-tab]");
const artifactPanels = document.querySelectorAll("[data-artifact-panel]");
const sampleButtons = document.querySelectorAll("[data-sample]");
const workbenchGrid = document.querySelector("[data-resizable-workbench]");
const workspaceResizer = document.querySelector("#workspace-resizer");
const providerDiagnostics = document.querySelector("#provider-diagnostics");

const CUSTOM_SELECT_SOURCES = [
  providerModeSetting,
  providerPresetSelect,
  providerProviderSelect,
  providerProfileSelect,
];
const WORKBENCH_WIDTH_KEY = "papershield.workbench.leftWidth.v1";
const DEFAULT_CONTROL_WIDTH = 340;
const MIN_CONTROL_WIDTH = 292;
const MAX_CONTROL_WIDTH = 520;
const MIN_REVIEW_WIDTH = 420;

const STATUS_LABELS = {
  "accepted": "已通过",
  "below_threshold": "低于质量阈值",
  "fallback": "已保留原文",
  "analysis_only": "仅分析",
  "pending": "待处理",
};

const RISK_FLAG_LABELS = {
  "fallback_original_retained": "原文兜底保留",
  "below_quality_threshold": "低于质量阈值",
  "citation_retention_risk": "引注保留风险",
  "template_word_residue": "模板化表达残留",
  "sentence_variation_reduced": "句式变化下降",
  "provider_warning": "模型调用警告",
  "unchanged_output": "润色结果未变化",
  "semantic_addition_risk": "疑似新增事实",
  "term_change_risk": "术语变化风险",
};

const CHOICE_LABELS = {
  rewritten: "采纳润色",
  original: "保留原文",
};

const RECOMMENDATION_LABELS = {
  accept: "建议采纳",
  review: "建议复核",
  keep_original: "建议保留原文",
};

const DOMAIN_LABELS = {
  law: "法学",
  economics: "经济学",
  general: "通用社科领域",
};

const WORKFLOW_ROUTE_LABELS = {
  quality_accepted: "质量通过",
  manual_review_required: "需要人工复核",
  unknown: "未知路线",
};

const WORKFLOW_NODE_LABELS = {
  parse_document: "解析文档",
  process_paragraphs: "处理正文",
  review_gate: "质量门禁",
  quality_accepted: "质量通过分支",
  manual_review_required: "人工复核分支",
  aggregate_review: "汇总建议",
  assemble_output: "生成输出",
};

const SAMPLE_DRAFTS = {
  law: {
    label: "法学样例",
    domain: "law",
    text: `一、问题提出

此外，数据安全问题在平台治理中日益突出[1]。因此，现有法律规制需要进一步完善。综上所述，这一问题对于数字经济发展具有重要意义。

图1 数据治理链路

值得注意的是，个人信息处理行为与数据交易秩序之间存在复杂关联(张三, 2021)。此外，司法实践仍然需要在法益识别和注意义务之间形成更稳定的判断路径。

参考文献
[1] 张三：《数据法研究》，北京大学出版社，2021。`,
  },
  economics: {
    label: "经济样例",
    domain: "economics",
    text: `二、模型设定

此外，市场失灵需要政府干预[2]。因此，现有政策设计具有重要意义。

表1 变量定义

References

Smith, 2020.`,
  },
  general: {
    label: "通用社科样例",
    domain: "general",
    text: `1. 研究背景

综上所述，平台治理需要进一步完善(李四, 2022)。

图1 平台治理结构`,
  },
};

let currentPayload = null;
let paragraphChoices = new Map();
let providerPresets = new Map();
let currentProviderConfig = null;
let runtimePolicy = null;
let customSelects = new Map();

initializeCustomSelects();
initializeWorkbenchResizer();
loadRuntimePolicy();
loadProviderSettings();
updateRequestEstimate();
activateArtifactTab("final");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setBusy(true);
  clearProviderAlert();
  setStatus("正在运行审阅工作流...", false);
  renderLoadingState();

  try {
    const formData = new FormData(form);
    const file = formData.get("file");
    if (!file || file.size === 0) {
      formData.delete("file");
    }
    const response = await fetch("/api/optimize", {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "请求失败");
    }
    renderResult(payload);
    if (payload.provider_error && payload.provider_error.failed) {
      const message = payload.provider_error.all_fallback ? "模型调用失败，已保留原文" : "模型调用部分失败，请检查段落警告";
      setStatus(message, true);
      setProviderAlert(`${message}。${payload.provider_error.message || "请检查模型设置。"}`, true);
      activateArtifactTab("evidence");
    } else {
      setStatus(payload.analysis_only ? "仅分析报告已生成" : "审阅报告已生成", false);
      activateArtifactTab("final");
    }
    if (Number.isFinite(payload.paragraph_count)) {
      renderRequestEstimate(payload.paragraph_count);
    }
  } catch (error) {
    renderErrorState(error.message);
    setStatus(error.message, true);
    setProviderAlert(error.message, true);
  } finally {
    setBusy(false);
  }
});

providerConfigForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await saveProviderConfig();
});

providerModeSetting.addEventListener("change", () => {
  syncProviderMode();
  updateRequestEstimate();
});

providerPresetSelect.addEventListener("change", () => {
  applyPresetToForm(providerPresetSelect.value);
});

clearProviderKeyButton.addEventListener("click", async () => {
  await clearProviderKey();
});

textInput.addEventListener("input", updateRequestEstimate);
fileInput.addEventListener("change", () => {
  updateFileName();
  updateRequestEstimate();
});
analysisOnlyInput.addEventListener("change", updateRequestEstimate);

for (const button of sampleButtons) {
  button.addEventListener("click", () => {
    const sample = SAMPLE_DRAFTS[button.dataset.sample];
    if (!sample) return;
    textInput.value = sample.text;
    fileInput.value = "";
    updateFileName();
    setDomain(sample.domain);
    updateRequestEstimate();
    setStatus(`已载入${sample.label}草稿`, false);
  });
}

for (const tab of artifactTabs) {
  tab.addEventListener("click", () => activateArtifactTab(tab.dataset.artifactTab));
}

checkProviderButton.addEventListener("click", async () => {
  const providerData = new FormData();
  providerData.set("provider_mode", providerModeInput.value || "configured");
  checkProviderButton.disabled = true;
  setProviderStatus("检测中...", "busy");
  clearProviderAlert();
  try {
    if (providerApiKeyInput.value.trim()) {
      await saveProviderConfig({ silent: true });
    }
    const response = await fetch("/api/provider/check", {
      method: "POST",
      body: providerData,
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "连接失败");
    }
    setProviderStatus(payload.message || "连接可用", "success");
    setStatus("模型连接可用", false);
  } catch (error) {
    setProviderStatus("连接失败", "error");
    setStatus(error.message, true);
    setProviderAlert(error.message, true);
  } finally {
    checkProviderButton.disabled = false;
  }
});

reviewWorkbench.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button || !currentPayload) return;

  const index = Number(button.dataset.index);
  const paragraph = currentPayload.paragraphs.find((item) => item.index === index);
  if (!paragraph) return;

  if (button.dataset.action === "copy-rewrite") {
    await copyText(paragraph.rewritten_text || "");
    setStatus(`已复制段落 ${index} 的润色稿`, false);
    return;
  }

  if (button.dataset.action === "accept-rewrite") {
    paragraphChoices.set(index, "rewritten");
    setStatus(`段落 ${index} 已选择采纳润色`, false);
  }
  if (button.dataset.action === "keep-original") {
    paragraphChoices.set(index, "original");
    setStatus(`段落 ${index} 已选择保留原文`, false);
  }
  renderReviewWorkbench(currentPayload.paragraphs);
  renderMergedFinalText();
});

copyFinalButton.addEventListener("click", async () => {
  await copyText(finalText.textContent || "");
  setStatus("已复制最终稿", false);
});

downloadMarkdownButton.addEventListener("click", () => {
  if (!currentPayload) {
    setStatus("请先运行诊断", true);
    return;
  }
  downloadFile("papershield-review.md", buildMarkdownReport(), "text/markdown;charset=utf-8");
  setStatus("已导出 Markdown 报告", false);
});

downloadHtmlButton.addEventListener("click", () => {
  if (!currentPayload) {
    setStatus("请先运行诊断", true);
    return;
  }
  downloadFile("papershield-review.html", buildHtmlReport(), "text/html;charset=utf-8");
  setStatus("已导出 HTML 报告", false);
});

downloadWordButton.addEventListener("click", async () => {
  if (!currentPayload) {
    setStatus("请先运行诊断", true);
    return;
  }
  await downloadWordReport();
});

async function loadProviderSettings() {
  try {
    const [presetsResponse, configResponse] = await Promise.all([
      fetch("/api/provider/presets"),
      fetch("/api/provider/config"),
    ]);
    const presetsPayload = await presetsResponse.json();
    const configPayload = await configResponse.json();
    if (!presetsResponse.ok) throw new Error(presetsPayload.detail || "厂商 preset 加载失败");
    if (!configResponse.ok) throw new Error(configPayload.detail || "模型配置加载失败");
    populateProviderPresets(presetsPayload);
    fillProviderForm(configPayload);
    if (runtimePolicy && runtimePolicy.provider_config_enabled === false) {
      applyRuntimePolicy(runtimePolicy);
    } else {
      clearProviderAlert();
    }
  } catch (error) {
    providerSummary.textContent = "模型配置加载失败";
    setProviderAlert(error.message, true);
  }
}

async function loadRuntimePolicy() {
  try {
    const response = await fetch("/api/runtime/policy");
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "运行策略加载失败");
    }
    runtimePolicy = payload;
    applyRuntimePolicy(payload);
  } catch (error) {
    runtimePolicy = null;
  }
}

function applyRuntimePolicy(policy) {
  const locked = policy && policy.provider_config_enabled === false;
  const controls = [
    providerPresetSelect,
    providerProviderSelect,
    providerBaseUrlInput,
    providerModelInput,
    providerApiKeyInput,
    providerProfileSelect,
    providerTimeoutInput,
    providerMaxRetriesInput,
    providerModeSetting,
    checkProviderButton,
    clearProviderKeyButton,
    document.querySelector("#save-provider"),
  ];
  for (const control of controls) {
    if (control) control.disabled = Boolean(locked);
  }
  providerConfigForm.classList.toggle("locked-mode", Boolean(locked));
  syncAllCustomSelects();
  if (locked) {
    setProviderStatus("公开演示模式", "locked");
    setProviderAlert("公开演示模式已锁定模型配置。", false);
  }
}

function populateProviderPresets(payload) {
  providerPresets = new Map();
  providerPresetSelect.innerHTML = "";
  const customOption = document.createElement("option");
  customOption.value = "custom";
  customOption.textContent = "自定义";
  providerPresetSelect.appendChild(customOption);
  for (const group of payload.groups || []) {
    const optgroup = document.createElement("optgroup");
    optgroup.label = group.label;
    for (const preset of group.presets || []) {
      providerPresets.set(preset.id, preset);
      const option = document.createElement("option");
      option.value = preset.id;
      option.textContent = preset.label;
      optgroup.appendChild(option);
    }
    providerPresetSelect.appendChild(optgroup);
  }
  syncCustomSelect(providerPresetSelect);
}

function fillProviderForm(config) {
  currentProviderConfig = config;
  providerPresetSelect.value = config.preset_id || "custom";
  providerProviderSelect.value = config.provider || "openai-compatible";
  providerBaseUrlInput.value = config.base_url || "";
  providerModelInput.value = config.model || "";
  providerApiKeyInput.value = "";
  providerProfileSelect.value = config.prompt_profile || "default";
  providerTimeoutInput.value = config.timeout || 120;
  providerMaxRetriesInput.value = Number.isFinite(config.max_retries) ? config.max_retries : 0;
  providerModeSetting.value = config.provider === "mock" ? "mock" : "configured";
  syncProviderMode();
  setProviderStatus(config.configured ? "已配置" : "未配置 API key", config.configured ? "success" : "warning");
  providerSummary.textContent = buildProviderSummary(config);
  syncAllCustomSelects();
}

function applyPresetToForm(presetId) {
  const preset = providerPresets.get(presetId);
  if (!preset) return;
  providerProviderSelect.value = preset.provider;
  providerBaseUrlInput.value = preset.base_url || "";
  providerModelInput.value = preset.default_model || "";
  providerModeSetting.value = preset.provider === "mock" ? "mock" : "configured";
  if (preset.provider !== "mock") {
    providerMaxRetriesInput.value = providerMaxRetriesInput.value || 0;
  }
  syncProviderMode();
  syncAllCustomSelects();
  setProviderAlert(preset.note || "", false);
}

async function saveProviderConfig(options = {}) {
  if (runtimePolicy && runtimePolicy.provider_config_enabled === false) {
    setProviderAlert("公开演示模式已锁定模型配置。", false);
    return currentProviderConfig;
  }
  const payload = readProviderForm();
  if (providerApiKeyInput.value.trim()) {
    payload.api_key = providerApiKeyInput.value.trim();
  }
  if (options.clearKey) {
    payload.clear_api_key = true;
  }
  const response = await fetch("/api/provider/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.detail || "模型配置保存失败");
    if (!options.silent) setProviderAlert(error.message, true);
    throw error;
  }
  fillProviderForm(result);
  if (!options.silent) {
    setProviderAlert("模型设置已保存。API key 仅保存在当前后端进程内，页面不会回显。", false);
    setStatus("模型设置已保存", false);
  }
  return result;
}

async function clearProviderKey() {
  providerApiKeyInput.value = "";
  await saveProviderConfig({ clearKey: true });
  setProviderAlert("API key 已从当前后端进程清空。", false);
}

function readProviderForm() {
  if (providerModeSetting.value === "mock") {
    return {
      preset_id: "mock",
      provider: "mock",
      base_url: "",
      model: "mock",
      prompt_profile: providerProfileSelect.value || "default",
      timeout: toBoundedInt(providerTimeoutInput.value, 120, 1),
      max_retries: 0,
    };
  }
  return {
    preset_id: providerPresetSelect.value || "custom",
    provider: providerProviderSelect.value || "openai-compatible",
    base_url: providerBaseUrlInput.value.trim(),
    model: providerModelInput.value.trim(),
    prompt_profile: providerProfileSelect.value || "default",
    timeout: toBoundedInt(providerTimeoutInput.value, 120, 1),
    max_retries: toBoundedInt(providerMaxRetriesInput.value, 0, 0),
  };
}

function syncProviderMode() {
  const useMock = providerModeSetting.value === "mock";
  providerModeInput.value = useMock ? "mock" : "configured";
  if (useMock) {
    providerPresetSelect.value = "mock";
    providerProviderSelect.value = "mock";
    providerBaseUrlInput.value = "";
    providerModelInput.value = "mock";
  }
  providerConfigForm.classList.toggle("mock-mode", useMock);
  syncAllCustomSelects();
}

function buildProviderSummary(config) {
  if (config.provider === "mock") {
    return "当前使用：本地演示模型（无需 API key）";
  }
  const keyState = config.api_key_present ? "密钥已配置" : "尚未配置密钥";
  const base = config.base_url_configured ? "服务地址已设置" : "服务地址未设置";
  return `当前使用：外部模型 · ${config.model || "未选择模型"} · ${keyState} · ${base}`;
}

function initializeCustomSelects() {
  for (const select of CUSTOM_SELECT_SOURCES.filter(Boolean)) {
    if (customSelects.has(select)) continue;
    select.classList.add("custom-select-source");
    select.setAttribute("aria-hidden", "true");
    select.tabIndex = -1;

    const root = document.createElement("div");
    root.className = "custom-select";
    root.dataset.selectId = select.id;

    const trigger = document.createElement("button");
    trigger.className = "custom-select-trigger";
    trigger.type = "button";
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");

    const value = document.createElement("span");
    value.className = "custom-select-value";

    const caret = document.createElement("span");
    caret.className = "custom-select-caret";
    caret.setAttribute("aria-hidden", "true");
    caret.textContent = "⌄";

    const list = document.createElement("div");
    list.className = "custom-select-list";
    list.id = `${select.id}-listbox`;
    list.role = "listbox";
    list.hidden = true;

    trigger.setAttribute("aria-controls", list.id);
    trigger.append(value, caret);
    root.append(trigger, list);
    select.insertAdjacentElement("afterend", root);

    const state = { select, root, trigger, value, list };
    customSelects.set(select, state);

    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      toggleCustomSelect(state);
    });
    trigger.addEventListener("keydown", (event) => handleCustomSelectTriggerKeydown(event, state));
    list.addEventListener("click", (event) => {
      const option = event.target.closest("[data-custom-option]");
      if (!option || option.getAttribute("aria-disabled") === "true") return;
      chooseCustomSelectOption(state, option.dataset.value);
    });
    list.addEventListener("keydown", (event) => handleCustomSelectListKeydown(event, state));
    select.addEventListener("change", () => syncCustomSelect(select));
    syncCustomSelect(select);
  }

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".custom-select")) closeAllCustomSelects();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeAllCustomSelects();
  });
}

function syncAllCustomSelects() {
  for (const select of customSelects.keys()) {
    syncCustomSelect(select);
  }
}

function syncCustomSelect(select) {
  const state = customSelects.get(select);
  if (!state) return;
  const options = readCustomSelectOptions(select);
  const selected = options.find((option) => option.value === select.value) || options[0];

  state.value.textContent = selected ? selected.label : "请选择";
  state.trigger.disabled = Boolean(select.disabled);
  state.trigger.title = selected ? selected.label : "";
  state.root.classList.toggle("is-disabled", Boolean(select.disabled));

  state.list.innerHTML = "";
  let lastGroup = null;
  for (const option of options) {
    if (option.group && option.group !== lastGroup) {
      const groupLabel = document.createElement("div");
      groupLabel.className = "custom-select-group";
      groupLabel.textContent = option.group;
      state.list.appendChild(groupLabel);
      lastGroup = option.group;
    }
    const item = document.createElement("div");
    item.className = "custom-select-option";
    item.dataset.customOption = "true";
    item.dataset.value = option.value;
    item.id = `${select.id}-option-${slugForId(option.value)}`;
    item.role = "option";
    item.tabIndex = -1;
    item.textContent = option.label;
    item.setAttribute("aria-selected", String(option.value === select.value));
    item.setAttribute("aria-disabled", String(option.disabled));
    if (option.disabled) item.classList.add("is-disabled");
    state.list.appendChild(item);
  }
}

function readCustomSelectOptions(select) {
  const options = [];
  for (const child of select.children) {
    if (child.tagName === "OPTGROUP") {
      for (const option of child.children) {
        if (option.tagName !== "OPTION") continue;
        options.push({
          value: option.value,
          label: option.textContent || option.value,
          group: child.label || "",
          disabled: Boolean(child.disabled || option.disabled),
        });
      }
    } else if (child.tagName === "OPTION") {
      options.push({
        value: child.value,
        label: child.textContent || child.value,
        group: "",
        disabled: Boolean(child.disabled),
      });
    }
  }
  return options;
}

function toggleCustomSelect(state) {
  if (state.trigger.disabled) return;
  if (state.root.classList.contains("open")) {
    closeCustomSelect(state);
  } else {
    openCustomSelect(state);
  }
}

function openCustomSelect(state) {
  if (state.trigger.disabled) return;
  syncCustomSelect(state.select);
  closeAllCustomSelects(state);
  state.root.classList.add("open");
  state.list.hidden = false;
  state.trigger.setAttribute("aria-expanded", "true");
  window.requestAnimationFrame(() => focusSelectedCustomOption(state));
}

function closeCustomSelect(state) {
  state.root.classList.remove("open");
  state.list.hidden = true;
  state.trigger.setAttribute("aria-expanded", "false");
}

function closeAllCustomSelects(exceptState = null) {
  for (const state of customSelects.values()) {
    if (state !== exceptState) closeCustomSelect(state);
  }
}

function chooseCustomSelectOption(state, value) {
  const option = Array.from(state.select.options).find((item) => item.value === value);
  if (!option || option.disabled || state.select.disabled) return;
  state.select.value = value;
  state.select.dispatchEvent(new Event("change", { bubbles: true }));
  syncCustomSelect(state.select);
  closeCustomSelect(state);
  state.trigger.focus();
}

function handleCustomSelectTriggerKeydown(event, state) {
  if (["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) {
    event.preventDefault();
    openCustomSelect(state);
    if (event.key === "ArrowUp") focusLastCustomOption(state);
  }
}

function handleCustomSelectListKeydown(event, state) {
  if (event.key === "Escape") {
    event.preventDefault();
    closeCustomSelect(state);
    state.trigger.focus();
    return;
  }
  if (event.key === "Enter" || event.key === " ") {
    const option = event.target.closest("[data-custom-option]");
    if (option) {
      event.preventDefault();
      chooseCustomSelectOption(state, option.dataset.value);
    }
    return;
  }
  if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
    event.preventDefault();
    focusCustomOptionByKey(state, event.key);
  }
}

function focusSelectedCustomOption(state) {
  const selected = Array.from(state.list.querySelectorAll("[data-custom-option]"))
    .find((option) => option.getAttribute("aria-selected") === "true" && option.getAttribute("aria-disabled") !== "true");
  const first = state.list.querySelector('[data-custom-option][aria-disabled="false"]');
  (selected || first || state.trigger).focus();
}

function focusLastCustomOption(state) {
  const options = Array.from(state.list.querySelectorAll('[data-custom-option][aria-disabled="false"]'));
  (options[options.length - 1] || state.trigger).focus();
}

function focusCustomOptionByKey(state, key) {
  const options = Array.from(state.list.querySelectorAll('[data-custom-option][aria-disabled="false"]'));
  if (!options.length) return;
  const currentIndex = Math.max(0, options.indexOf(document.activeElement));
  const nextIndex = key === "Home"
    ? 0
    : key === "End"
      ? options.length - 1
      : key === "ArrowUp"
        ? Math.max(0, currentIndex - 1)
        : Math.min(options.length - 1, currentIndex + 1);
  options[nextIndex].focus();
}

function slugForId(value) {
  return String(value || "empty").replace(/[^a-z0-9_-]+/gi, "-").replace(/^-+|-+$/g, "") || "option";
}

function initializeWorkbenchResizer() {
  if (!workbenchGrid || !workspaceResizer) return;

  setControlRailWidth(readStoredControlWidth() || DEFAULT_CONTROL_WIDTH, false);

  workspaceResizer.addEventListener("pointerdown", (event) => {
    if (!isResizableWorkbench()) return;
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = getCurrentControlWidth();
    document.body.classList.add("is-resizing");
    workspaceResizer.setPointerCapture(event.pointerId);

    const handleMove = (moveEvent) => {
      setControlRailWidth(startWidth + moveEvent.clientX - startX, false);
    };
    const handleEnd = () => {
      document.body.classList.remove("is-resizing");
      workspaceResizer.removeEventListener("pointermove", handleMove);
      storeControlWidth(getCurrentControlWidth());
    };

    workspaceResizer.addEventListener("pointermove", handleMove);
    workspaceResizer.addEventListener("pointerup", handleEnd, { once: true });
    workspaceResizer.addEventListener("pointercancel", handleEnd, { once: true });
  });

  workspaceResizer.addEventListener("keydown", (event) => {
    if (!isResizableWorkbench()) return;
    const current = getCurrentControlWidth();
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      setControlRailWidth(current - 16, true);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      setControlRailWidth(current + 16, true);
    } else if (event.key === "Home") {
      event.preventDefault();
      setControlRailWidth(MIN_CONTROL_WIDTH, true);
    } else if (event.key === "End") {
      event.preventDefault();
      setControlRailWidth(MAX_CONTROL_WIDTH, true);
    }
  });

  workspaceResizer.addEventListener("dblclick", () => {
    setControlRailWidth(DEFAULT_CONTROL_WIDTH, true);
  });

  window.addEventListener("resize", () => {
    setControlRailWidth(getCurrentControlWidth(), false);
  });
}

function isResizableWorkbench() {
  return window.matchMedia("(min-width: 921px)").matches;
}

function getControlWidthBounds() {
  const gridWidth = workbenchGrid ? workbenchGrid.getBoundingClientRect().width : 0;
  const hasArtifactColumn = window.matchMedia("(min-width: 1241px)").matches;
  const artifactReserve = hasArtifactColumn ? 360 : 0;
  const maxBySpace = gridWidth ? gridWidth - artifactReserve - MIN_REVIEW_WIDTH - 72 : MAX_CONTROL_WIDTH;
  const max = Math.max(MIN_CONTROL_WIDTH, Math.min(MAX_CONTROL_WIDTH, maxBySpace));
  return { min: MIN_CONTROL_WIDTH, max };
}

function setControlRailWidth(width, persist) {
  const bounds = getControlWidthBounds();
  const numericWidth = Number.parseInt(width, 10);
  const clamped = Math.round(Math.min(bounds.max, Math.max(bounds.min, Number.isFinite(numericWidth) ? numericWidth : DEFAULT_CONTROL_WIDTH)));
  document.documentElement.style.setProperty("--control-width", `${clamped}px`);
  workspaceResizer.setAttribute("aria-valuenow", String(clamped));
  workspaceResizer.setAttribute("aria-valuemax", String(Math.round(bounds.max)));
  if (persist) storeControlWidth(clamped);
}

function getCurrentControlWidth() {
  const value = getComputedStyle(document.documentElement).getPropertyValue("--control-width");
  return Number.parseInt(value, 10) || DEFAULT_CONTROL_WIDTH;
}

function readStoredControlWidth() {
  try {
    return Number.parseInt(window.localStorage.getItem(WORKBENCH_WIDTH_KEY), 10);
  } catch (error) {
    return null;
  }
}

function storeControlWidth(width) {
  try {
    window.localStorage.setItem(WORKBENCH_WIDTH_KEY, String(width));
  } catch (error) {
    // localStorage may be unavailable in locked-down demo contexts.
  }
}

function updateRequestEstimate() {
  const count = estimateParagraphCount(textInput.value);
  renderRequestEstimate(count);
}

function renderRequestEstimate(paragraphCount) {
  const multiplier = analysisOnlyInput.checked ? 1 : 2;
  const minimumRequests = analysisOnlyInput.checked ? 1 : Math.max(1, paragraphCount) * multiplier;
  const file = fileInput.files && fileInput.files[0];
  const fileNote = file ? "；上传文件以实际解析段落为准" : "";
  const quotaNote = paragraphCount >= 20 ? "；长文档可能快速消耗免费额度" : "";
  const modeNote = analysisOnlyInput.checked ? "文章级分析" : `双层润色：${Math.max(1, paragraphCount)} 段 × ${multiplier}`;
  requestEstimate.textContent = `最低请求数估算：${minimumRequests} 次（${modeNote}）${fileNote}${quotaNote}`;
}

function estimateParagraphCount(value) {
  const text = String(value || "").trim();
  if (!text) return 1;
  return text.split(/\n\s*\n+/).map((part) => part.trim()).filter(Boolean).length || 1;
}

function setStatus(message, isError) {
  statusBox.textContent = message;
  statusBox.classList.toggle("error", Boolean(isError));
}

function setProviderStatus(message, state = "neutral") {
  const text = String(message || "未测试").trim() || "未测试";
  providerStatus.textContent = compactStatusText(text, 42);
  providerStatus.title = text;
  providerStatus.dataset.state = state;
}

function compactStatusText(value, limit) {
  const text = String(value || "");
  if (text.length <= limit) return text;
  return `${text.slice(0, limit)}...`;
}

function setProviderAlert(message, isError) {
  const text = String(message || "").trim();
  if (providerDiagnostics) {
    providerDiagnostics.hidden = !text;
    providerDiagnostics.open = false;
    providerDiagnostics.classList.toggle("error", Boolean(isError));
  }
  providerAlert.hidden = !text;
  providerAlert.textContent = text;
  providerAlert.classList.toggle("error", Boolean(isError));
}

function clearProviderAlert() {
  setProviderAlert("", false);
}

function setBusy(isBusy) {
  runButton.disabled = Boolean(isBusy);
  runButton.textContent = isBusy ? "诊断中..." : "运行诊断";
  document.body.classList.toggle("is-busy", Boolean(isBusy));
}

function renderLoadingState() {
  setResultControlsEnabled(false);
  resultSummary.innerHTML = `
    <div>
      <p class="kicker">Review State</p>
      <h2>正在审阅</h2>
    </div>
    <div class="loading-shell" aria-label="结果加载中">
      <span class="skeleton-line"></span>
      <span class="skeleton-line short"></span>
    </div>
  `;
  reviewWorkbench.innerHTML = `
    <div class="skeleton-card">
      <span class="skeleton-line short"></span>
      <span class="skeleton-line"></span>
      <span class="skeleton-line"></span>
      <span class="skeleton-line short"></span>
    </div>
  `;
  finalText.textContent = "正在等待 Agent 输出...";
  metricsBox.innerHTML = '<div class="empty-line">指标计算中...</div>';
  workflowTrace.innerHTML = '<div class="empty-line">工作流执行中...</div>';
  reviewItems.innerHTML = "<li>等待诊断完成...</li>";
}

function renderErrorState(message) {
  resultSummary.innerHTML = `
    <div>
      <p class="kicker">Review State</p>
      <h2>运行失败</h2>
    </div>
    <p>${escapeHtml(message)}</p>
  `;
  reviewWorkbench.innerHTML = `
    <div class="empty-state">
      <strong>无法生成审阅结果</strong>
      <span>${escapeHtml(message)}</span>
    </div>
  `;
  finalText.textContent = "等待运行...";
}

function renderResult(payload) {
  currentPayload = payload;
  paragraphChoices = new Map((payload.paragraphs || []).map((paragraph) => [
    paragraph.index,
    paragraph.status === "fallback" ? "original" : "rewritten",
  ]));
  setResultControlsEnabled(true);
  renderResultSummary(payload);
  renderMergedFinalText();
  renderMetrics(payload.metrics || {});
  renderWorkflowTrace(payload.workflow || {});
  if (payload.analysis_only) {
    renderAnalysisSummary(payload.analysis_summary || {}, payload.paragraphs || []);
  } else {
    renderReviewWorkbench(payload.paragraphs || []);
  }
  renderReviewItems(payload.review_items || []);
}

function renderResultSummary(payload) {
  const metrics = payload.metrics || {};
  const workflow = payload.workflow || {};
  const fallbackCount = Number.isFinite((payload.provider_error || {}).fallback_count)
    ? payload.provider_error.fallback_count
    : (payload.paragraphs || []).filter((paragraph) => paragraph.status === "fallback").length;
  const title = workflow.manual_review_required ? "需要人工复核" : "审阅完成";
  const rows = [
    ["段落", String(payload.paragraph_count || (payload.paragraphs || []).length || 0)],
    ["路线", formatWorkflowRouteLabel(workflow.route)],
    ["引用保留", formatPercent(metrics.average_citation_retention)],
    ["兜底", `${fallbackCount} 段`],
  ];
  resultSummary.innerHTML = `
    <div>
      <p class="kicker">Review State</p>
      <h2>${escapeHtml(title)}</h2>
    </div>
    <div class="summary-grid">
      ${rows.map(([label, value]) => `<div class="summary-item"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}
    </div>
  `;
}

function renderMetrics(metrics) {
  const rows = [
    ["困惑度代理", formatNumber(metrics.average_rewritten_perplexity)],
    ["模板词减少率", formatPercent(metrics.average_template_reduction)],
    ["引用保留率", formatPercent(metrics.average_citation_retention)],
    ["困惑度变化", formatPercent(metrics.average_perplexity_change, true)],
  ];
  metricsBox.innerHTML = rows
    .map(([label, value]) => `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");
}

function renderWorkflowTrace(workflow) {
  const steps = Array.isArray(workflow.steps) && workflow.steps.length
    ? workflow.steps
    : (Array.isArray(workflow.nodes) ? workflow.nodes.map((node) => ({ id: node, label: WORKFLOW_NODE_LABELS[node] || node, description: "" })) : []);
  const nodeList = steps.length
    ? steps.map((step, index) => renderWorkflowStep(step, index)).join("")
    : '<div class="empty-line">等待运行</div>';
  const rows = [
    ["后端", workflow.backend_label || workflow.backend || "未知"],
    ["路线", workflow.route_label || formatWorkflowRouteLabel(workflow.route)],
    ["人工复核", workflow.manual_review_label || (workflow.manual_review_required ? "已触发" : "未触发")],
  ];
  workflowTrace.innerHTML = `
    <div class="workflow-summary">
      ${rows.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}
    </div>
    <div class="workflow-nodes">${nodeList}</div>
  `;
}

function renderWorkflowStep(step, index) {
  const label = step.label || WORKFLOW_NODE_LABELS[step.id] || "工作流步骤";
  const description = step.description || "该步骤已完成。";
  return `<div class="workflow-node" data-step="${index + 1}">
    <span>
      <strong>${escapeHtml(label)}</strong>
      <small>${escapeHtml(description)}</small>
    </span>
  </div>`;
}

function renderAnalysisSummary(summary, paragraphs) {
  const scope = summary.scope || {};
  const groups = [
    ["优势", summary.strengths || []],
    ["主要问题", summary.issues || []],
    ["建议", summary.suggestions || []],
  ];
  reviewWorkbench.innerHTML = `
    <section class="analysis-card" aria-label="文章级分析结果">
      <header class="analysis-card-head">
        <div>
          <p class="kicker">Article Analysis</p>
          <h3>文章级诊断简述</h3>
        </div>
        <span class="recommendation">仅分析</span>
      </header>
      <p class="analysis-overview">${escapeHtml(summary.overview || "已完成文章级诊断，请结合下方要点复核正文质量。")}</p>
      <div class="analysis-scope">
        <span>正文段落 ${escapeHtml(scope.analyzed_paragraphs ?? paragraphs.length ?? 0)}</span>
        <span>跳过非正文块 ${escapeHtml(scope.skipped_blocks ?? 0)}</span>
      </div>
      <div class="analysis-grid">
        ${groups.map(([label, values]) => renderAnalysisGroup(label, values)).join("")}
      </div>
    </section>
  `;
}

function renderAnalysisGroup(label, values) {
  const items = Array.isArray(values) && values.length ? values : ["暂无明显条目，仍建议人工复核。"];
  return `<section class="analysis-group">
    <h4>${escapeHtml(label)}</h4>
    <ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
  </section>`;
}

function renderReviewWorkbench(paragraphs) {
  if (!paragraphs.length) {
    reviewWorkbench.innerHTML = `
      <div class="empty-state">
        <strong>暂无段落</strong>
        <span>请提供文本或上传文档后重新运行。</span>
      </div>
    `;
    return;
  }
  reviewWorkbench.innerHTML = paragraphs.map(renderParagraphReviewCard).join("");
}

function renderParagraphReviewCard(paragraph) {
  const choice = paragraphChoices.get(paragraph.index) || "rewritten";
  const flagLabels = formatParagraphRiskFlagList(paragraph);
  const recommendation = paragraph.recommendation_label || formatRecommendationLabel(paragraph.recommendation);
  const flags = flagLabels.length
    ? flagLabels.map((flag) => `<span class="badge">${escapeHtml(flag)}</span>`).join("")
    : '<span class="badge muted-badge">无风险标记</span>';
  const metrics = paragraph.metrics
    ? `<span class="badge muted-badge">引用 ${formatPercent(paragraph.metrics.citation_retention)}</span><span class="badge muted-badge">模板 ${formatPercent(paragraph.metrics.template_reduction)}</span>`
    : "";
  return `<section class="review-card" data-index="${paragraph.index}" aria-label="段落 ${paragraph.index} 审阅">
    <header class="review-card-head">
      <div class="review-card-title">
        <strong>段落 ${paragraph.index} · ${escapeHtml(formatParagraphStatusLabel(paragraph))}</strong>
        <div class="card-badges">${flags}${metrics}</div>
      </div>
      <span class="recommendation">${escapeHtml(recommendation)}</span>
    </header>
    <div class="comparison-grid">
      <div class="text-cell ${choice === "original" ? "selected-cell" : ""}">
        <span class="text-label">原文</span>
        <p>${escapeHtml(paragraph.original_text || "")}</p>
      </div>
      <div class="text-cell ${choice === "rewritten" ? "selected-cell" : ""}">
        <span class="text-label">润色稿</span>
        <p>${escapeHtml(paragraph.rewritten_text || "")}</p>
      </div>
    </div>
    <div class="diff-row">
      <span class="text-label">差异</span>
      <p>${renderDiffSegments(paragraph.diff_segments || [])}</p>
    </div>
    <div class="actions">
      <button class="choice-button ${choice === "rewritten" ? "active" : ""}" data-action="accept-rewrite" data-index="${paragraph.index}" type="button" aria-pressed="${choice === "rewritten"}">采纳润色</button>
      <button class="choice-button ${choice === "original" ? "active" : ""}" data-action="keep-original" data-index="${paragraph.index}" type="button" aria-pressed="${choice === "original"}">保留原文</button>
      <button class="secondary-button" data-action="copy-rewrite" data-index="${paragraph.index}" type="button">复制润色</button>
    </div>
  </section>`;
}

function renderDiffSegments(segments) {
  if (!segments.length) {
    return '<span class="diff-equal">无差异</span>';
  }
  return segments
    .map((segment) => {
      const op = ["equal", "delete", "insert"].includes(segment.op) ? segment.op : "equal";
      return `<span class="diff-${op}">${escapeHtml(segment.text)}</span>`;
    })
    .join("");
}

function renderMergedFinalText() {
  if (!currentPayload) {
    finalText.textContent = "等待运行...";
    return;
  }
  finalText.textContent = buildMergedText();
}

function buildMergedText() {
  const paragraphs = currentPayload.paragraphs || [];
  const documentBlocks = currentPayload.document_blocks || [];
  if (documentBlocks.length) {
    return documentBlocks
      .map((block) => renderDocumentBlock(block, paragraphs))
      .filter((part) => part)
      .join("\n\n");
  }

  if (paragraphs.length) {
    return paragraphs.map(selectedParagraphText).join("\n\n");
  }
  return currentPayload.final_text || "";
}

function renderDocumentBlock(block, paragraphs) {
  if (block.kind === "paragraph") {
    const paragraph = paragraphs.find((item) => item.index === block.paragraph_report_index);
    return paragraph ? selectedParagraphText(paragraph) : "";
  }
  return block.text || "";
}

function selectedParagraphText(paragraph) {
  const choice = paragraphChoices.get(paragraph.index) || "rewritten";
  return choice === "original" ? paragraph.original_text || "" : paragraph.rewritten_text || "";
}

function renderReviewItems(items) {
  if (!items.length) {
    reviewItems.innerHTML = "<li>未发现额外段落级风险；仍建议人工复核事实、术语、论点和引注。</li>";
    return;
  }
  reviewItems.innerHTML = items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function setResultControlsEnabled(enabled) {
  copyFinalButton.disabled = !enabled;
  downloadMarkdownButton.disabled = !enabled;
  downloadHtmlButton.disabled = !enabled;
  downloadWordButton.disabled = !enabled;
}

function buildMarkdownReport() {
  const metrics = currentPayload.metrics || {};
  const workflow = currentPayload.workflow || {};
  const lines = [
    "# PaperShield 审阅报告",
    "",
    `生成时间: ${formatDateTime(new Date())}`,
    `领域: ${formatDomainLabel(currentPayload.domain)}`,
    `Prompt profile: ${currentPayload.prompt_profile || "default"}`,
    "",
  ];

  if (currentPayload.provider_error && currentPayload.provider_error.failed) {
    lines.push("## 模型调用状态");
    lines.push("");
    lines.push(`- ${currentPayload.provider_error.message || "模型调用失败，已保留原文"}`);
    lines.push("");
  }

  lines.push("## 最终稿");
  lines.push("");
  lines.push(buildMergedText());
  lines.push("");
  lines.push("## 组合指标");
  lines.push("");
  lines.push(`- 困惑度代理: ${formatNumber(metrics.average_rewritten_perplexity)}`);
  lines.push(`- 模板词减少率: ${formatPercent(metrics.average_template_reduction)}`);
  lines.push(`- 引用保留率: ${formatPercent(metrics.average_citation_retention)}`);
  lines.push(`- 困惑度变化: ${formatPercent(metrics.average_perplexity_change, true)}`);
  lines.push("");
  lines.push("## 工作流轨迹");
  lines.push("");
  lines.push(`- 后端: ${workflow.backend_label || workflow.backend || "未知"}`);
  lines.push(`- 路线: ${workflow.route_label || formatWorkflowRouteLabel(workflow.route)}`);
  lines.push(`- 人工复核: ${workflow.manual_review_label || (workflow.manual_review_required ? "已触发" : "未触发")}`);
  const workflowSteps = workflow.steps || [];
  if (workflowSteps.length) {
    for (const step of workflowSteps) {
      lines.push(`- ${step.label || WORKFLOW_NODE_LABELS[step.id] || "工作流步骤"}: ${step.description || ""}`);
    }
  }
  lines.push("");
  if (currentPayload.analysis_only && currentPayload.analysis_summary) {
    const summary = currentPayload.analysis_summary;
    lines.push("## 文章级分析");
    lines.push("");
    lines.push(summary.overview || "");
    lines.push("");
    for (const [label, values] of [["优势", summary.strengths || []], ["主要问题", summary.issues || []], ["建议", summary.suggestions || []]]) {
      lines.push(`### ${label}`);
      for (const value of values) lines.push(`- ${value}`);
      lines.push("");
    }
  }
  lines.push("## 逐段审阅");
  lines.push("");

  for (const paragraph of currentPayload.paragraphs || []) {
    const choice = paragraphChoices.get(paragraph.index) || "rewritten";
    lines.push(`### 段落 ${paragraph.index}`);
    lines.push("");
    lines.push(`- 当前选择: ${formatChoiceLabel(choice)}`);
    lines.push(`- 状态: ${formatParagraphStatusLabel(paragraph)}`);
    lines.push(`- 建议: ${paragraph.recommendation_label || formatRecommendationLabel(paragraph.recommendation)}`);
    lines.push(`- 风险标记: ${formatParagraphRiskFlagList(paragraph).join("、") || "无"}`);
    lines.push("");
    lines.push("原文:");
    lines.push("");
    lines.push(paragraph.original_text || "");
    lines.push("");
    lines.push("润色稿:");
    lines.push("");
    lines.push(paragraph.rewritten_text || "");
    lines.push("");
  }

  lines.push("## 人工复核清单");
  lines.push("");
  const items = currentPayload.review_items || [];
  if (items.length) {
    for (const item of items) {
      lines.push(`- ${item}`);
    }
  } else {
    lines.push("- 复核事实、术语、论点和引注位置是否与原文一致。");
  }
  lines.push("");
  lines.push("## 合规提示");
  lines.push("");
  lines.push("- 指标为本地代理信号，不代表任何外部 AI 检测器结果。");
  lines.push("- 请人工复核事实、术语、论点和引注。");
  lines.push("- 仅用于你有权编辑的学术草稿。");
  return lines.join("\n");
}

function buildHtmlReport() {
  const markdown = buildMarkdownReport();
  const body = markdown
    .split("\n")
    .map((line) => `<p>${escapeHtml(line) || "&nbsp;"}</p>`)
    .join("\n");
  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>PaperShield 审阅报告</title>
    <style>
      body { max-width: 920px; margin: 40px auto; color: #17201d; background: #f1efe4; font-family: Georgia, "Microsoft YaHei", serif; line-height: 1.7; }
      p { margin: 0 0 8px; white-space: pre-wrap; }
    </style>
  </head>
  <body>
    ${body}
  </body>
</html>`;
}

async function downloadWordReport() {
  setStatus("正在生成 Word 报告...", false);
  try {
    const response = await fetch("/api/report/docx", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        payload: currentPayload,
        choices: Object.fromEntries([...paragraphChoices.entries()].map(([index, choice]) => [String(index), choice])),
      }),
    });
    if (!response.ok) {
      let message = "Word 报告生成失败";
      try {
        const payload = await response.json();
        message = payload.detail || message;
      } catch (error) {
        // Non-JSON error bodies are handled by the fallback message.
      }
      throw new Error(message);
    }
    downloadBlob("papershield-review.docx", await response.blob());
    setStatus("已导出 Word 报告", false);
  } catch (error) {
    setStatus(error.message, true);
    setProviderAlert(error.message, true);
  }
}

function downloadFile(filename, content, type) {
  const blob = new Blob([content], { type });
  downloadBlob(filename, blob);
}

function downloadBlob(filename, blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function activateArtifactTab(name) {
  for (const tab of artifactTabs) {
    const active = tab.dataset.artifactTab === name;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  }
  for (const panel of artifactPanels) {
    const active = panel.dataset.artifactPanel === name;
    panel.hidden = !active;
    panel.classList.toggle("active", active);
  }
}

function updateFileName() {
  const file = fileInput.files && fileInput.files[0];
  fileName.textContent = file ? `已选择：${file.name}` : "未选择文件，粘贴文本也可以直接运行。";
}

function setDomain(domain) {
  const input = document.querySelector(`input[name="domain"][value="${domain}"]`);
  if (input) input.checked = true;
}

function formatStatusLabel(status) {
  return STATUS_LABELS[status] || "未知状态";
}

function formatRiskFlagLabel(flag) {
  return RISK_FLAG_LABELS[flag] || "未知风险";
}

function formatChoiceLabel(choice) {
  return CHOICE_LABELS[choice] || "未选择";
}

function formatRecommendationLabel(recommendation) {
  return RECOMMENDATION_LABELS[recommendation] || "建议复核";
}

function formatDomainLabel(domain) {
  return DOMAIN_LABELS[domain] || "未指定";
}

function formatWorkflowRouteLabel(route) {
  return WORKFLOW_ROUTE_LABELS[route] || WORKFLOW_ROUTE_LABELS.unknown;
}

function formatRiskFlagList(flags) {
  return (flags || []).map(formatRiskFlagLabel);
}

function formatParagraphStatusLabel(paragraph) {
  return paragraph.status_label || formatStatusLabel(paragraph.status);
}

function formatParagraphRiskFlagList(paragraph) {
  if (Array.isArray(paragraph.risk_flag_labels) && paragraph.risk_flag_labels.length) {
    return paragraph.risk_flag_labels;
  }
  return formatRiskFlagList(paragraph.risk_flags);
}

async function copyText(value) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const helper = document.createElement("textarea");
  helper.value = value;
  helper.setAttribute("readonly", "");
  helper.style.position = "fixed";
  helper.style.opacity = "0";
  document.body.appendChild(helper);
  helper.select();
  document.execCommand("copy");
  document.body.removeChild(helper);
}

function toBoundedInt(value, fallback, minimum) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed >= minimum ? parsed : fallback;
}

function formatNumber(value) {
  return Number.isFinite(value) ? value.toFixed(2) : "-";
}

function formatPercent(value, signed = false) {
  if (!Number.isFinite(value)) return "-";
  const sign = signed && value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}%`;
}

function formatDateTime(date) {
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (char) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    };
    return entities[char];
  });
}
