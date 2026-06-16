# AGENT 开发文档

## 项目定位

这个项目是一个本地 Windows 桌面小工具：用 Tkinter 做悬浮球，用本机 Codex 会话快照中的 `token_count.rate_limits` 展示额度窗口。

第一原则：安全和可解释性优先。不要读取浏览器 cookie、登录 token、`auth.json`、密码、会话密钥或其他敏感凭据。不要关闭、重启、杀掉或控制 Codex 进程。不要把 `data/`、`logs/` 中的本机运行数据打进发布包。

## 当前正确方案

- 数据来源：`~/.codex/sessions/**/rollout-*.jsonl` 中最新的 `rate_limits`。
- 数据生成：`src/codex_bubble/codex_usage_fetcher.py` 解析会话快照，写入 `data/codex_usage_data.json`。
- 后台同步：`src/codex_bubble/codex_usage_daemon.py` 每 60 秒运行一次读取器。
- 桌面 UI：`src/codex_bubble/floating_info_ball.py` 读取 `config/` 和 `data/`，展示 5 小时/1 周额度窗口。
- 桌面 UI 启动时会自动确保后台同步器在运行；后台同步器必须有单实例锁，避免重复启动。
- 用户入口：根目录只保留中文启动文件 `启动悬浮球.bat`。
- 卸载入口：安装目录应包含中文卸载文件 `卸载悬浮球.bat`，普通用户不需要进入脚本目录。
- 未连接状态：所有额度值和重置时间显示为 `-`，不要使用示例百分比伪装真实数据。

## 目录约定

- `src/codex_bubble/`：只放应用源码。
- `config/`：放默认配置和可编辑配置。
- `data/`：运行时生成的数据，必须被 `.gitignore` 忽略。
- `logs/`：运行时日志，必须被 `.gitignore` 忽略。
- 运行时目录不可写时，自动回退到 `%LOCALAPPDATA%\CodexBubble`。
- 在 git 开发仓库里运行时，运行时配置、数据和日志必须写到用户运行目录，不得写脏 tracked 的默认 `config/` 文件。
- `scripts/`：维护脚本使用英文命名。
- `docs/`：中文说明文档和方案记录。
- `scripts/installer/`：安装器内部脚本，负责当前用户安装、快捷方式和覆盖升级。
- `docs/assets/codex-bubble.ico`：应用图标，安装器、快捷方式和 Tk 窗口应尽量共用这一个文件。
- `releases/`：本地构建输出目录，发布产物不得提交到 Git；Release 由 CI 构建并上传安装器。
- `VERSION`：当前版本号。
- `CHANGELOG.md`：版本更新日志。
- `.github/workflows/release.yml`：推送 `v*` tag 后自动创建 GitHub Release。

## 开发方向

1. 稳定本地额度解析：优先兼容 Codex 会话快照字段变化，解析失败时给出清晰日志。
2. 打磨 Windows 桌面体验：悬浮球拖动、展开、右键菜单、屏幕边界和高 DPI 行为要稳定。
3. 保持用户入口简单：普通用户只需要双击 `启动悬浮球.bat`。
4. 在线更新以“检查 GitHub Release 并打开新版安装器”为主；安装器负责退出旧版进程并覆盖升级，不在运行中的 UI 里直接改写安装目录。
5. 面向用户的 Release 必须是 Windows 安装器 `.exe`，不要再把 zip 源码包作为主要下载物。
6. 文档中文优先：用户使用说明用中文；维护脚本和源码命名保持英文。

## 多屏交互约定

- 使用 Windows `EnumDisplayMonitors` / `GetMonitorInfoW` 获取每个显示器的工作区。
- 允许窗口保存负坐标，支持副屏在主屏左侧或上方的布局。
- 拖动时不要按主屏 `0..screen_w` 边界夹住窗口，也不要在拖动过程中夹取位置；拖动结束后只把窗口夹回鼠标所在显示器的工作区。
- 透明悬浮窗拖动时不要切换成非透明外壳；窗口移动统一使用 Tk `geometry`，不要用 Win32 `SetWindowPos` 移动 Tk 透明窗口，避免固定在左上角或出现黑块。
- 右键菜单优先使用系统原生菜单，避免自绘菜单被悬浮窗透明层遮挡、定位异常或截断。
- 如果保存的位置对应的显示器已移除，把窗口移动到最近的可用显示器工作区内。
- 悬浮球应提供系统托盘找回入口。双击托盘图标要定位悬浮球并给出短暂位置提示；主窗口不应在任务栏显示 Python 默认图标。
- 分辨率变化、显示器拔插或重新登录后，应通过可见性看门狗把窗口夹回可用工作区。

## 不做的事

- 不接入 cookie/token/auth.json。
- 不引导用户导出或粘贴敏感凭据。
- 不执行用户环境变量提供的额度命令。
- 不调用 ChatGPT/Codex 远程额度接口。
- 不关闭、重启、杀掉或控制 Codex 进程。
- 不在更新检查时自动覆盖本地安装目录。
- 不把本机 `data/codex_usage_data.json`、日志、缓存、`.git` 打包。
- 不为了视觉效果引入重型 GUI 框架，除非明确决定重写桌面端。

## 修改前检查

- 先运行 `git status -sb`，确认是否有用户未提交改动。
- 修改源码后运行：

```powershell
python -m py_compile src\codex_bubble\runtime_paths.py src\codex_bubble\single_instance.py src\codex_bubble\update_checker.py src\codex_bubble\floating_info_ball.py src\codex_bubble\codex_usage_fetcher.py src\codex_bubble\codex_usage_daemon.py
```

- 准备发布前必须运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1
```

- 任何功能追加或 BUG 修复，必须本地核验通过后才能打包、打 tag 或推送 GitHub Release。
- 如果自动化无法验证某个行为，必须在本机运行软件，让用户确认后再继续。
- 如果界面、交互或外观发生变化，必须更新 `docs/assets/` 中的截图，并同步更新 `README.md` 的预览图或说明。
- 开发临时文件、缓存、日志、运行时数据必须加入 `.gitignore`，也必须从发布包中排除。

- 修改启动流程后至少检查这些脚本路径：
  - `启动悬浮球.bat`
  - `卸载悬浮球.bat`
  - `scripts/run_codex_local_usage_once.bat`
  - `scripts/start_codex_usage_daemon_local.bat`
  - `scripts/install_local_usage_startup.ps1`
- 修改启动流程后必须验证重复启动行为：悬浮球和后台同步器都不能多开。

## 安装器发布规则

安装器内部 payload 应包含：

- `启动悬浮球.bat`
- `卸载悬浮球.bat`
- `src/`
- `config/`
- `scripts/`
- `docs/`
- `README.md`
- `AGENTS.md`
- `VERSION`
- `CHANGELOG.md`
- `docs/assets/codex-bubble.ico`

安装器内部 payload 不应包含：

- `.git/`
- `data/`
- `logs/`
- `__pycache__/`
- `*.log`
- 本机生成的 `codex_usage_data.json`

面向 GitHub Release 的用户下载物应命名为 `codex-bubble-setup-vX.Y.Z.exe`。zip 只能作为安装器内部 payload 或本地临时验证材料，不应作为主要 Release 资产上传。

## GitHub 发布纪律

- 使用 `scripts\build_release.ps1` 生成安装器。
- 使用 `scripts\verify_release.ps1` 核验安装器和内部 payload。
- PR 必须等待 `.github/workflows/pr-review.yml` 的 `PR Review Gate` 通过；该门禁会跑空白检查、安装器构建、payload 检查、临时安装和卸载烟测，并上传短期安装器 artifact 供人工检查。
- 核验失败时禁止推送 `v*` tag。
- 核验失败时禁止触发 GitHub Release。
- GitHub Actions 必须在 tag 触发后现场构建安装器并上传 `.exe`，不要要求仓库里预先提交二进制发布包。
- 自动化无法覆盖的界面交互，必须记录人工确认结果后再发布。
- 如果发现临时文件进入 Git 状态或发布包，必须先修 `.gitignore` 和构建脚本，再重新核验。
