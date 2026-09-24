# edu-ops-dashboard

校管家数据采集、标准化和经营指标计算骨架。

第一版采用“双通道”设计：

- 主通道：Playwright 登录态复用后直接请求校管家接口。
- 兜底通道：Chrome/Playwright UI 导出 Excel，再进入同一套标准化流程。

## 当前已完成

- P0 工程骨架：`src/` 布局、pytest、ruff、pre-commit、CI、日志和数据分层目录。
- P1 规则固化：人工月配置、下载前检查、下载后文件校验、运行记录。
- P2 接口适配器：已实测课消汇总接口，以及排课列表 `Course/QueryNew` 的分页 JSON 明细；排课采集通过已登录页面触发真实请求，不保存动态认证头，UI 导出仍保留为兜底。
- 标准 `ScheduleRecord` 数据结构，以及明确区分的周平均课次、周平均课时、预排/生产课时和人工月工具。
- 指标写入 PostgreSQL 时同时保留带 `snapshot_date` 的预排快照，重复运行按同一快照幂等更新，不覆盖其他日期的历史判断。

## 快速开始

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run edu-ops --today 2026-09-13
```

当前命令会读取 `config/manual_months.csv`，输出当前日期对应的人工月区间。增加 `--collect-schedule --headed` 可通过已登录页面采集排课 JSON，并在失败时自动切换 UI 导出；完整说明见 `docs/运行部署.md`。

### V0.1 经营看板与 Widget 数据边界（历史入口）

Python 业务层生成唯一的 [Dashboard Data Contract](docs/DASHBOARD_DATA_CONTRACT.md)，网页、`/api/status`、`/widget-data.json` 和 Android Widget 都消费同一份 JSON。Android 不解析 Excel，也不重新计算经营指标。

使用已下载的 Excel 生成网页/API 和离线文件：

```bash
./start-dashboard.sh \
  --input "/path/to/排课列表.xlsx" \
  --one-to-one-students 100 \
  --total-students 200 \
  --export-json ./widget-data.json
```

该段描述的是 V0.1。Standalone Widget V0.2 的主流程改为下方的一次性本地生成与 JSON 导入，不再内置经营样例数据。

### Standalone Widget V0.2

```bash
uv sync --extra excel --extra dev
uv run edu-ops-widget \\
  --input "/path/to/排课列表.xlsx" \\
  --output "/path/to/widget-data.json"
```

省略 `--input` 时，会在 `~/Downloads` 和 `~/Desktop` 查找最新的 `排课列表_*.xls` 或 `排课列表_*.xlsx`。Android 首次安装显示“尚未导入数据”；通过“导入最新经营数据”选择 JSON 后，Widget 使用本地最近成功缓存，断网可查看。Android SDK 缺失，因此构建和设备验证仍未完成。详见 [Standalone Widget V0.2 状态](STANDALONE_WIDGET_V02_STATUS.md)。

### 本地经营指标卡片（只读）

使用昨天已经下载的排课 Excel，不会触发下载：

```bash
./start-dashboard.sh --input "/path/to/排课列表.xlsx"
```

省略 `--input` 时会从 `~/Downloads` 和 `~/Desktop` 自动选择最近的 `排课列表_*` 文件。启动后终端会打印 Mac 本机地址和局域网 Android 地址；页面刷新只重新读取同一份输入。

## 数据安全

- 原始 JSON/XLSX 只放在本地 `data/raw/`，默认不会进入 Git。
- 认证信息只存在浏览器 context 的运行时 Cookie jar 中，不写入源码或 `.env`。
- 云端只接收脱敏后的聚合指标；PostgreSQL 中的 Metabase 应用库和业务库分开。

## 目录

```text
src/edu_ops/       业务代码
config/            人工月等配置
data/raw/          原始文件（本地）
data/interim/      中间数据
data/processed/    脱敏后的处理结果
docs/              架构、口径和操作记录
infra/             PostgreSQL / Metabase 部署骨架
tests/             单元测试
```
