# 真实 Codex 额度接入方式

结论：

- 个人 Plus/Pro 目前没有公开稳定的 `codex usage --json` 或 `codex status --json`。
- Codex App/CLI 的 `/status` 可以显示 rate limits，但官方文档没有给外部脚本用的机器可读参数。
- OpenAI API 的 token usage 和 Flex processing 都不是 Codex 订阅额度查询。
- Business/Enterprise 的 Analytics API/Compliance API 可做统计和审计，但数据可能滞后，不等同于 5 小时窗口实时剩余。

## 方法 1：本地 Codex 会话快照，当前默认

运行：

```powershell
python .\codex_usage_fetcher.py
```

或双击：

```text
start_codex_usage_daemon_local.bat
```

原理：

- 扫描 `~/.codex/sessions/**/rollout-*.jsonl`。
- 找最新的 `token_count` 事件。
- 提取其中的 `rate_limits.primary` 和 `rate_limits.secondary`。
- 转成悬浮球使用的 `codex_usage_data.json`。

示例输出：

```json
{
  "usage_windows": {
    "five_hour": { "label": "5小时", "remaining": "75%", "reset": "17:57" },
    "weekly": { "label": "1周", "remaining": "93%", "reset": "6月22日" }
  }
}
```

这是当前最安全、最可分享的方法：别人运行时读取的是他自己电脑上的 Codex 会话快照。

## 方法 2：自定义命令

如果以后你有自己的 CLI 能输出 JSON：

```powershell
$env:CODEX_USAGE_COMMAND = "your-command-that-prints-json"
python .\codex_usage_fetcher.py
```

JSON 结构同上。

## 方法 3：授权 API

如果你有明确授权的 API：

```powershell
$env:CODEX_USAGE_URL = "https://your-safe-usage-api.example.com/usage"
python .\codex_usage_fetcher.py
```

不要把浏览器 cookie、Codex cookie、ChatGPT session token 放进这里。

## 方法 4：/wham/usage 实验模式

Codex 桌面端内部会请求：

```text
https://chatgpt.com/backend-api/wham/usage
```

fetcher 支持显式授权 token 的实验模式：

```powershell
$env:CODEX_USAGE_SOURCE = "wham"
$env:CODEX_ACCESS_TOKEN = "你明确授权使用的 Codex access token"
python .\codex_usage_fetcher.py
```

限制：

- 这不是公开稳定 API。
- 不适合分享版。
- 不要从本地私有存储中提取 token。

## 开机启动

推荐本地快照版：

```powershell
powershell -ExecutionPolicy Bypass -File .\install_local_usage_startup.ps1
```

取消：

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_local_usage_startup.ps1
```
