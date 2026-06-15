# 真实额度数据方案

当前项目只保留本机 Codex 会话快照方案。

## 正确数据来源

读取本机 Codex 会话目录：

```text
~/.codex/sessions/**/rollout-*.jsonl
```

读取器会查找最新的 `token_count.rate_limits` 或兼容的 `rate_limits` 字段，并转换为悬浮球使用的：

```text
data/codex_usage_data.json
```

## 手动刷新

```powershell
scripts\run_codex_local_usage_once.bat
```

或直接运行：

```powershell
python src\codex_bubble\codex_usage_fetcher.py
```

## 后台同步

```powershell
scripts\start_codex_usage_daemon_local.bat
```

后台同步器每 60 秒刷新一次。

## 开机启动

安装：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_local_usage_startup.ps1
```

取消：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall_local_usage_startup.ps1
```

## 不再保留的旧方案

以下方案已经废弃，不应重新加入：

- 读取 cookie
- 读取 token
- 读取 auth.json
- 调用需要用户登录凭据的远程接口
- 把本机额度数据预置进分享包
