# 免费部署指南

PaperShield 可以用 GitHub + Render 免费 Web Service 部署。默认模型仍是本地 `mock`，不会消耗模型额度；若你在 Render 中设置访问口令，登录用户可以在网页里填写外部模型信息并调用真实模型。

## 推荐路径：GitHub + Render 免费 Web Service

这条路径最适合公开作品集：从 `main` 分支自动部署，后续你推送到 GitHub 后，线上服务会自动更新。

1. 将仓库推送到 GitHub。
2. 在 Render 创建新的 Blueprint 或 Web Service，并连接这个 GitHub 仓库。
3. 使用仓库内置 `render.yaml`：
   - `plan: free`
   - `runtime: docker`
   - `healthCheckPath: /healthz`
   - `PAPERSHIELD_LLM_PROVIDER=mock`
   - `PAPERSHIELD_PROVIDER_CONFIG_ENABLED=1`
   - `PAPERSHIELD_ADMIN_TOKEN` 使用 `sync: false`，需要在 Render 环境变量界面手动填写，不写入仓库
4. 部署完成后打开 `/healthz`，确认 `status` 为 `ok`。
5. 打开网站首页，先确认“用户须知”，再在“模型与运行环境”面板输入访问口令，填写模型服务地址、模型 ID 和 API key，点击“测试连接”与“保存设置”。

Render 免费服务在长时间无人访问后可能休眠，休眠后的第一次请求会慢一些，这是免费方案的正常现象。

## 已有 Render 服务的补充设置

如果服务已经创建，但模型配置仍不可用，请进入 Render 的服务页面：

1. 打开 `Environment`。
2. 添加或确认以下变量：

```env
PAPERSHIELD_LLM_PROVIDER=mock
PAPERSHIELD_PROVIDER_CONFIG_ENABLED=1
PAPERSHIELD_ADMIN_TOKEN=<你自己设置的访问口令>
PAPERSHIELD_PROMPT_PROFILE=default
```

3. 保存后触发一次 `Manual Deploy`，或推送一个新提交到 GitHub 触发自动部署。
4. 部署完成后访问 `/api/runtime/policy`，确认 `provider_config_enabled` 为 `true`，`admin_token_required` 为 `true`。

`PAPERSHIELD_ADMIN_TOKEN` 是网页登录模型配置区的访问口令。它不是模型 API key，不要写进 README、代码或提交记录。

## 公开演示环境

如果只想做安全的公开演示，不让访问者配置真实模型，可以使用：

```env
PAPERSHIELD_LLM_PROVIDER=mock
PAPERSHIELD_PROVIDER_CONFIG_ENABLED=0
PAPERSHIELD_PROMPT_PROFILE=default
```

这种模式下网页仍可运行本地 mock 诊断，但模型配置区会被锁定。

## 真实模型环境

如果要让可信用户登录后配置并调用外部模型，推荐使用：

```env
PAPERSHIELD_LLM_PROVIDER=mock
PAPERSHIELD_PROVIDER_CONFIG_ENABLED=1
PAPERSHIELD_ADMIN_TOKEN=<在平台环境变量中设置>
```

然后由登录用户在网页中填写：

- 模型厂商预设或自定义服务地址；
- 模型/端点 ID；
- API key；
- 超时时间和失败重试次数。

后端只持久化非密钥字段；API key 仅保存在当前后端进程内。Render 免费服务重启或休眠恢复后，可能需要重新填写 API key。

## 其他免费路径

- Koyeb 免费实例：使用本仓库 `Dockerfile`，让平台注入 `PORT`，并设置同样的环境变量。
- Hugging Face Docker Space：适合公开作品集演示，创建 Space 时选择 Docker。
- Google Cloud Run 免费额度：有免费用量，但通常需要绑定账单。

无论使用哪条路径，都不要把真实 API key、访问口令或 `.env` 文件提交到 GitHub。
