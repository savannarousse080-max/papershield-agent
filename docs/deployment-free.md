# 免费部署指南

PaperShield 可以用 GitHub + Render 免费 Web Service 部署。默认模型仍是本地 `mock`，不会消耗模型额度；若你在 Render 中设置访问密匙和站点模型参数，可信用户登录后可以使用你提供的托管免费额度。用户也可以随时切换到“自备模型参数”，用自己的 API key 和额度调用产品功能。

## 推荐路径：GitHub + Render 免费 Web Service

这条路径最适合公开作品集：从 `main` 分支自动部署，后续你推送到 GitHub 后，线上服务会自动更新。

1. 将仓库推送到 GitHub。
2. 在 Render 创建新的 Blueprint 或 Web Service，并连接这个 GitHub 仓库。
3. 使用仓库内置 `render.yaml`：
   - `plan: free`
   - `runtime: docker`
   - `healthCheckPath: /healthz`
   - `PAPERSHIELD_LLM_PROVIDER=mock`
   - `PAPERSHIELD_PROVIDER_CONFIG_ENABLED=0`
   - `PAPERSHIELD_ADMIN_TOKEN` 使用 `sync: false`，需要在 Render 环境变量界面手动填写，不写入仓库
   - `PAPERSHIELD_CONFIG_ADMIN_TOKEN` 使用 `sync: false`，建议单独填写并只由站长保存
   - `PAPERSHIELD_HOSTED_FREE_RUN_LIMIT=3`
4. 部署完成后打开 `/healthz`，确认 `status` 为 `ok`。
5. 在 Render 环境变量中配置你的托管模型参数和 API key。打开网站首页，可信用户确认“用户须知”后输入访问密匙，即可使用托管免费额度；需要自备额度时切换到“自备模型参数”。

Render 免费服务在长时间无人访问后可能休眠，休眠后的第一次请求会慢一些，这是免费方案的正常现象。

## 已有 Render 服务的补充设置

如果服务已经创建，但模型配置仍不可用，请进入 Render 的服务页面：

1. 打开 `Environment`。
2. 添加或确认以下变量：

```env
PAPERSHIELD_LLM_PROVIDER=mock
PAPERSHIELD_PROVIDER_CONFIG_ENABLED=0
PAPERSHIELD_ADMIN_TOKEN=<你自己设置的访问口令>
PAPERSHIELD_CONFIG_ADMIN_TOKEN=<站点配置管理员口令>
PAPERSHIELD_REQUIRE_ADMIN_TOKEN_FOR_PROVIDER_USE=1
PAPERSHIELD_HOSTED_FREE_RUN_LIMIT=3
PAPERSHIELD_PROMPT_PROFILE=default
```

3. 如果要让托管额度调用真实模型，还需要设置 `PAPERSHIELD_LLM_PROVIDER`、`PAPERSHIELD_LLM_MODEL`、`PAPERSHIELD_LLM_BASE_URL` 和对应 API key。
4. 保存后触发一次 `Manual Deploy`，或推送一个新提交到 GitHub 触发自动部署。
5. 部署完成后访问 `/api/runtime/policy`，确认 `provider_config_enabled` 为 `true`，`admin_token_required` 为 `true`，`hosted_free_run_limit` 为预期次数。

`PAPERSHIELD_ADMIN_TOKEN` 是网页登录托管免费额度的访问密匙。它不是模型 API key，不要写进 README、代码或提交记录。`PAPERSHIELD_CONFIG_ADMIN_TOKEN` 是可选的站点配置管理员密匙；设置后，可信用户拿到的访问密匙只能使用托管额度，不能保存或覆盖你的站点默认模型参数。Render 公网环境中，如果没有设置访问密匙，后端会自动锁定模型配置区，即使 `PAPERSHIELD_PROVIDER_CONFIG_ENABLED=1` 也不会开放配置接口。`PAPERSHIELD_HOSTED_FREE_RUN_LIMIT` 默认是 3，当前实现按“访问密匙 + 浏览器客户端 ID”在当前后端进程内计数；服务重启后计数会清空。自备模型参数模式不消耗站点托管额度。

## 公开演示环境

如果只想做安全的公开演示，不让访问者配置真实模型，可以使用：

```env
PAPERSHIELD_LLM_PROVIDER=mock
PAPERSHIELD_PROVIDER_CONFIG_ENABLED=0
PAPERSHIELD_PROMPT_PROFILE=default
```

这种模式下网页仍可运行本地 mock 诊断，但模型配置区会被锁定。

## 托管额度环境

如果要让可信用户登录后使用你提供的模型额度，推荐使用：

```env
PAPERSHIELD_LLM_PROVIDER=openai-compatible
PAPERSHIELD_LLM_BASE_URL=<模型服务 HTTPS 地址>
PAPERSHIELD_LLM_MODEL=<模型或 endpoint id>
PAPERSHIELD_API_KEY=<在平台环境变量中设置>
PAPERSHIELD_PROVIDER_CONFIG_ENABLED=1
PAPERSHIELD_ADMIN_TOKEN=<在平台环境变量中设置>
PAPERSHIELD_CONFIG_ADMIN_TOKEN=<站长专用，建议不同于访问密匙>
PAPERSHIELD_HOSTED_FREE_RUN_LIMIT=3
```

可信用户输入访问密匙后会自动使用这些站点模型参数。用户需要使用自己的额度时，在网页中切换到“自备模型参数”并填写：

- 模型厂商预设或自定义服务地址；
- 模型/端点 ID；
- API key；
- 超时时间和失败重试次数。

自备模型参数只用于本次请求，不会写入站点默认配置。站点默认配置只应由你维护；不要把真实 API key 写入仓库。

## 其他免费路径

- Koyeb 免费实例：使用本仓库 `Dockerfile`，让平台注入 `PORT`，并设置同样的环境变量。
- Hugging Face Docker Space：适合公开作品集演示，创建 Space 时选择 Docker。
- Google Cloud Run 免费额度：有免费用量，但通常需要绑定账单。

无论使用哪条路径，都不要把真实 API key、访问口令或 `.env` 文件提交到 GitHub。
