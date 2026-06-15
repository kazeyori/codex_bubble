# AGENT 开发文档

## 项目定位

这个项目是一个本地 Windows 桌面小工具：用 Tkinter 做悬浮球，用本机 Codex 会话快照中的 `token_count.rate_limits` 展示额度窗口。

第一原则：安全和可解释性优先。不要读取浏览器 cookie、登录 token、`auth.json`、密码、会话密钥或其他敏感凭据。不要关闭、重启、杀掉或控制 Codex 进程。不要把 `data/`、`logs/` 中的本机运行数据打进发布包。

## 当前正确方案

- 数据来源：`~/.codex/sessions/**/rollout-*.jsonl` 中最新的 `rate_limits`。
- 数据生成：`src/codex_bubble/codex_usage_fetcher.py` 解析会话快照，写入 `data/codex_usage_data.json`。
- 后台同步：`src/codex_bubble/codex_usage_daemon.py` 每 60 秒运行一次读取器。
- 桌面 UI：`src/codex_bubble/floating_info_ball.py` 读取 `config/` 和 `data/`，展示 5 小时/1 周额度窗口。
- 用户入口：根目录只保留中文启动文件 `启动悬浮球.bat`。
- 未连接状态：所有额度值和重置时间显示为 `-`，不要使用示例百分比伪装真实数据。

## 目录约定

- `src/codex_bubble/`：只放应用源码。
- `config/`：放默认配置和可编辑配置。
- `data/`：运行时生成的数据，必须被 `.gitignore` 忽略。
- `logs/`：运行时日志，必须被 `.gitignore` 忽略。
- `scripts/`：维护脚本使用英文命名。
- `docs/`：中文说明文档和方案记录。
- `releases/`：发布压缩包，压缩包内不得包含本机真实额度数据或日志。
- `VERSION`：当前版本号。
- `CHANGELOG.md`：版本更新日志。

## 开发方向

1. 稳定本地额度解析：优先兼容 Codex 会话快照字段变化，解析失败时给出清晰日志。
2. 打磨 Windows 桌面体验：悬浮球拖动、展开、右键菜单、屏幕边界和高 DPI 行为要稳定。
3. 保持用户入口简单：普通用户只需要双击 `启动悬浮球.bat`。
4. 发布包可直接使用：发布前重新生成 `releases/codex-floating-info-ball-share.zip`。
5. 文档中文优先：用户使用说明用中文；维护脚本和源码命名保持英文。

## 多屏交互约定

- 使用 Windows `EnumDisplayMonitors` / `GetMonitorInfoW` 获取每个显示器的工作区。
- 允许窗口保存负坐标，支持副屏在主屏左侧或上方的布局。
- 拖动时不要按主屏 `0..screen_w` 边界夹住窗口，拖动结束后只把窗口夹回当前所在显示器的工作区。
- 右键菜单应在鼠标所在显示器的工作区内弹出。
- 如果保存的位置对应的显示器已移除，把窗口移动到最近的可用显示器工作区内。

## 不做的事

- 不接入 cookie/token/auth.json。
- 不引导用户导出或粘贴敏感凭据。
- 不执行用户环境变量提供的额度命令。
- 不调用 ChatGPT/Codex 远程额度接口。
- 不关闭、重启、杀掉或控制 Codex 进程。
- 不把本机 `data/codex_usage_data.json`、日志、缓存、`.git` 打包。
- 不为了视觉效果引入重型 GUI 框架，除非明确决定重写桌面端。

## 修改前检查

- 先运行 `git status -sb`，确认是否有用户未提交改动。
- 修改源码后运行：

```powershell
python -m py_compile src\codex_bubble\floating_info_ball.py src\codex_bubble\codex_usage_fetcher.py src\codex_bubble\codex_usage_daemon.py
```

- 修改启动流程后至少检查这些脚本路径：
  - `启动悬浮球.bat`
  - `scripts/run_codex_local_usage_once.bat`
  - `scripts/start_codex_usage_daemon_local.bat`
  - `scripts/install_local_usage_startup.ps1`

## 发布包规则

发布包应包含：

- `启动悬浮球.bat`
- `src/`
- `config/`
- `scripts/`
- `docs/`
- `README.md`
- `AGENTS.md`
- `VERSION`
- `CHANGELOG.md`

发布包不应包含：

- `.git/`
- `data/`
- `logs/`
- `__pycache__/`
- `*.log`
- 本机生成的 `codex_usage_data.json`
