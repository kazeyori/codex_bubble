# Codex 额度悬浮球

这是一个 Windows 桌面悬浮球，用来显示本机 Codex 的额度信息。

当前版本：`v0.1.2`

当前版本只保留正确方案：读取本机 Codex 会话快照里的 `rate_limits`，不读取 cookie，不读取 token，不读取 `auth.json`，不调用远程额度接口，也不会把本机实时额度数据打进分享包。

## 预览

折叠态：

![5小时折叠态](docs/assets/preview-chip-five-hour.png)
![1周折叠态](docs/assets/preview-chip-weekly.png)

展开态：

![展开面板](docs/assets/preview-panel.png)

## 快速启动

1. 从 GitHub Release 下载 `codex-bubble-v0.1.2.zip`，然后解压。
2. 确认电脑已安装 Python 3。
3. 双击根目录的 `启动悬浮球.bat`。
4. 如果显示“未连接”，额度和重置时间会显示为 `-`。先在这台电脑上使用 Codex 发一条消息，等待一分钟，或运行 `scripts/run_codex_local_usage_once.bat` 手动刷新一次。

## 安全边界

程序只读取本机 `.codex/sessions` 和 `.codex/archived_sessions` 下的会话快照文件，不会关闭、重启或控制 Codex 进程。

如果安装目录不可写，运行时配置、额度数据和日志会自动保存到 `%LOCALAPPDATA%\CodexBubble`。

## 多屏支持

悬浮球会识别 Windows 多显示器工作区，支持副屏在主屏左侧、右侧或上方的负坐标布局。拖到副屏后会保存当前位置；右键菜单会限制在鼠标所在屏幕内，不会弹到主屏之外看不见的地方。

## 在线更新

右键悬浮球，选择“检查更新”，软件会联网读取 GitHub 最新 Release。
如果发现新版本，会询问是否打开下载页面；当前版本不会自动覆盖本地文件，避免更新时误关正在使用的 Codex 或破坏现有安装。

## 单实例运行

应用默认不允许多开。重复双击 `启动悬浮球.bat` 时，已经运行的悬浮球会继续保留，新的悬浮球和后台同步器会自动退出。

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
├─ VERSION                         # 当前版本号
├─ CHANGELOG.md                    # 更新日志
└─ AGENTS.md                      # Agent/开发者协作规范
```

## 常用脚本

- `启动悬浮球.bat`：启动后台同步器和桌面悬浮球。
- 悬浮球启动时也会自动确保后台同步器在运行；重复启动会被单实例锁拦住，不会多开。
- `scripts/run_codex_local_usage_once.bat`：手动读取一次本机 Codex 会话快照。
- `scripts/start_codex_usage_daemon_local.bat`：只启动后台同步器。
- `scripts/install_local_usage_startup.ps1`：安装开机启动。
- `scripts/uninstall_local_usage_startup.ps1`：取消开机启动。

## 开发方向

后续开发请优先阅读 `AGENTS.md`。核心方向是：保持本地、安全、轻量，继续打磨 Windows 桌面体验，而不是接入敏感账号凭据、远程接口或会影响 Codex 进程的控制逻辑。
