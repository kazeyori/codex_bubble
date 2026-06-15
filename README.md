Codex 额度悬浮球
================

这是一个 Windows 桌面小悬浮球，用来显示本机 Codex 的额度信息。

当前版本只保留正确方案：读取本机 Codex 会话快照里的 `rate_limits`，不读取 cookie，不读取 token，不读取 `auth.json`，也不会把你的当前额度数据打进分享包。

用法
----

1. 下载或解压分享包。
2. 双击 `启动悬浮球.bat`。
3. 如果显示“未连接”，先在这台电脑上使用 Codex 发一条消息，等待一分钟或运行 `run_codex_local_usage_once.bat`。

开机启动
--------

右键 `install_local_usage_startup.ps1`，选择“使用 PowerShell 运行”。

取消开机启动时，右键运行 `uninstall_local_usage_startup.ps1`。

操作
----

- 左键单击：展开或收起
- 左键拖动：移动位置，位置会自动保存
- 右键单击：打开菜单
- 菜单里可以切换 `5小时` / `1周`、刷新、展开收起、退出

文件
----

- `floating_info_ball.py`：悬浮球主程序
- `floating_info_ball_config.json`：悬浮球配置和位置
- `codex_usage_fetcher.py`：读取本机 Codex 会话快照并生成额度数据
- `codex_usage_daemon.py`：每分钟运行一次读取器
- `启动悬浮球.bat`：给普通用户双击的中文启动入口
- `install_local_usage_startup.ps1`：安装开机启动
- `uninstall_local_usage_startup.ps1`：取消开机启动
- `run_codex_local_usage_once.bat`：手动刷新一次额度
- `start_codex_usage_daemon_local.bat`：只启动后台同步器
- `codex-floating-info-ball-share.zip`：可分享压缩包

安全说明
--------

这个版本不会读取浏览器 cookie、ChatGPT/Codex 登录态、token、`auth.json` 或密码。它只解析 Codex 本地会话快照里的 `token_count.rate_limits` 字段，用来显示剩余额度和刷新时间。
