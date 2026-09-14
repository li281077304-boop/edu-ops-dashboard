# Progress Board / Dashboard Cards

这是本地只读的经营指标卡片入口。它复用 `edu_ops` 现有 Excel adapter 和
metrics 引擎，不会触发校管家下载，也不会写 PostgreSQL。

在仓库根目录运行：

```bash
./start-dashboard.sh --input "/path/to/昨天的排课导出.xls"
```

省略 `--input` 时会从 `~/Downloads`、`~/Desktop` 中选择最近的 `排课列表_*` 文件。
服务会同时打印 Mac 本机地址和局域网 Android 地址。
