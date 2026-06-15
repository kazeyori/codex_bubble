# 安全读取真实 Codex 额度

当前版本首选 **本地会话快照法**：

- 读取 `~/.codex/sessions/**/rollout-*.jsonl`。
- 只解析 `token_count` 事件里的 `rate_limits` 字段。
- 不读取 `auth.json`、cookie、浏览器数据库、ChatGPT session token。
- 不需要 OpenAI API key，也不会把你的账号信息打包给别人。

悬浮球读取的数据文件是：

```text
codex_usage_data.json
```

同步器每分钟刷新一次。实际额度快照通常会在 Codex 完成一次 turn 后更新，所以如果你刚大量使用 Codex，等当前 turn 结束或再发一条消息，悬浮球会读到新的快照。

不要做这些事：

- 复制或解密 Codex/ChatGPT cookie。
- 把 session token 写进配置文件。
- 从浏览器或桌面应用私有存储中提取认证信息。

可选实验路线：

- 如果你有明确授权的 Codex access token，可以使用 `CODEX_USAGE_SOURCE=wham` 调用 `/wham/usage`。
- 如果你是 Business/Enterprise 管理员，可以用 Analytics API/Compliance API 做报表，但它们不是个人 5 小时窗口的实时剩余额度接口。
