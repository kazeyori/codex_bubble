Codex 额度悬浮球使用说明
========================

这是一个 Windows 桌面小悬浮球，用来显示本机 Codex 的额度信息。当前版本只保留正确方案：读取本机 Codex 会话快照里的 rate_limits，不读取 cookie，不读取 token，不读取 auth.json，也不会把你的当前额度数据打进分享包。

一、直接启动
------------

双击这个文件：

启动悬浮球.bat

它会同时启动两件事：桌面悬浮球，以及每分钟刷新一次的后台额度同步器。

如果悬浮球显示“未连接”，通常是因为这台电脑还没有新的 Codex 会话快照。打开 Codex 发一条消息后，再运行 run_codex_local_usage_once.bat，或者等后台同步器下一分钟刷新即可。

二、开机自动启动
----------------

右键下面这个文件，选择“使用 PowerShell 运行”：

install_local_usage_startup.ps1

它会在当前 Windows 用户的启动文件夹里创建快捷方式。以后登录 Windows 后，会自动启动“悬浮球 + 本地额度同步器”。

取消开机启动时，右键运行：

uninstall_local_usage_startup.ps1

三、手动刷新一次额度
--------------------

如果你想立即刷新，不想等后台同步器下一分钟运行，可以双击：

run_codex_local_usage_once.bat

它会读取本机 Codex 会话快照，生成或更新 codex_usage_data.json。这个文件只保存在你自己的电脑上，分享包里不会包含它。

四、只启动后台同步器
--------------------

一般不需要单独运行。如果悬浮球已经在运行，但后台同步器没开，可以双击：

start_codex_usage_daemon_local.bat

五、悬浮球操作
--------------

左键单击：展开或收起
左键拖动：移动位置，位置会自动保存
右键单击：打开菜单
菜单里可以切换 5小时 / 1周、刷新、展开收起、退出

六、文件说明
------------

floating_info_ball.py：悬浮球主程序
floating_info_ball_config.json：悬浮球配置和位置
codex_usage_fetcher.py：读取本机 Codex 会话快照并生成额度数据
codex_usage_daemon.py：每分钟运行一次读取器
启动悬浮球.bat：给普通用户双击的中文启动入口
install_local_usage_startup.ps1：安装开机启动
uninstall_local_usage_startup.ps1：取消开机启动
run_codex_local_usage_once.bat：手动刷新一次额度
start_codex_usage_daemon_local.bat：只启动后台同步器
codex_usage_data.json：运行后生成的本机额度数据，分享包不包含

七、分享给别人
--------------

把 codex-floating-info-ball-share.zip 发给别人即可。对方解压后双击“启动悬浮球.bat”。

对方看到的是他自己电脑上的 Codex 额度，不会看到你的额度，也不会使用你的账号信息。如果对方电脑还没有用过 Codex，需要先在那台电脑上使用 Codex 产生会话快照。

八、安全说明
------------

这个版本不会读取浏览器 cookie、ChatGPT/Codex 登录态、token、auth.json 或密码。它只解析 Codex 本地会话快照里的 token_count.rate_limits 字段，用来显示剩余额度和刷新时间。
