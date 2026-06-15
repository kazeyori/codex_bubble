# Codex 额度悬浮球

这是一个 Windows 桌面悬浮球，用来显示本机 Codex 的额度信息。

当前版本只保留正确方案：读取本机 Codex 会话快照里的 `rate_limits`，不读取 cookie，不读取 token，不读取 `auth.json`，不调用远程额度接口，也不会把本机实时额度数据打进分享包。

## 快速启动

1. 确认电脑已安装 Python 3。
2. 双击根目录的 `启动悬浮球.bat`。
3. 如果显示“未连接”，额度和重置时间会显示为 `-`。先在这台电脑上使用 Codex 发一条消息，等待一分钟，或运行 `scripts/run_codex_local_usage_once.bat` 手动刷新一次。

## 安全边界

程序只读取本机 `.codex/sessions` 和 `.codex/archived_sessions` 下的会话快照文件，不会关闭、重启或控制 Codex 进程。

## 项目结构

```text
.
├─ 启动悬浮球.bat                 # 普通用户双击入口
├─ src/codex_bubble/              # Python 源码
├─ config/                        # 默认配置
├─ data/                          # 本机生成的额度数据，不提交
├─ logs/                          # 运行日志，不提交
├─ scripts/                       # 英文维护脚本
├─ docs/                          # 中文使用、安全和方案文档
├─ releases/                      # 可分享压缩包
└─ AGENTS.md                      # Agent/开发者协作规范
```

## 常用脚本

- `启动悬浮球.bat`：启动后台同步器和桌面悬浮球。
- `scripts/run_codex_local_usage_once.bat`：手动读取一次本机 Codex 会话快照。
- `scripts/start_codex_usage_daemon_local.bat`：只启动后台同步器。
- `scripts/install_local_usage_startup.ps1`：安装开机启动。
- `scripts/uninstall_local_usage_startup.ps1`：取消开机启动。

## 开发方向

后续开发请优先阅读 `AGENTS.md`。核心方向是：保持本地、安全、轻量，继续打磨 Windows 桌面体验，而不是接入敏感账号凭据、远程接口或会影响 Codex 进程的控制逻辑。
