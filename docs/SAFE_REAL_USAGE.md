# 安全说明

当前版本的目标是“本地、安全、轻量”。

## 会读取什么

- 本机 Codex 会话快照中的 `rate_limits`。
- 悬浮球配置文件 `config/floating_info_ball_config.json`。
- 本机运行时额度数据 `data/codex_usage_data.json`。

## 不会读取什么

- 浏览器 cookie
- 登录 token
- `auth.json`
- 密码
- SSH key
- GitHub token
- 其他账号凭据

## 不会控制什么

- 不会关闭 Codex
- 不会重启 Codex
- 不会调用 `taskkill` 或 `Stop-Process`
- 不会执行环境变量中传入的自定义额度命令

## 发布包安全边界

发布包不得包含：

- `data/`
- `logs/`
- `codex_usage_data.json`
- `*.log`
- `.git/`
- `__pycache__/`

发布前请重新检查 `releases/codex-floating-info-ball-share.zip` 的内容。
