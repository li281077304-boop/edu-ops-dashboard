# edu-ops-dashboard

教学运营数据整理与经营指标计算工具。

## Standalone Android Widget V0.2

使用电脑上已经保存的单份排课表离线生成 Widget 数据。此流程仅读本地文件，不启动网页服务、不登录或下载数据，也不连接 PostgreSQL、Metabase 或 Payroll。

```bash
uv sync --extra excel
uv run edu-ops-widget --input "/path/to/排课列表.xlsx" --output "/path/to/widget-data.json"
```

支持 CSV、XLS、XLSX。省略 `--input` 时会在 Downloads 和 Desktop 中选择最近的 `排课列表_*.xls/.xlsx`。生成后在 Android App 点击“导入最新经营数据”并选择该 JSON；手机只验证并展示已计算指标。详情见 [Standalone Widget V0.2](docs/STANDALONE_WIDGET_V0.2.md)。

本地人工月范围来自 `config/manual_months.csv`，日期不属于唯一人工月、状态无法识别、关键字段缺失或发现完全重复行时，程序会停止输出，不会用 0 填补未知数据。

## 旧版工程流程

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

### 历史 V0.1 服务端看板（旧流程）

Python 业务层生成唯一的 [Dashboard Data Contract](docs/DASHBOARD_DATA_CONTRACT.md)，网页、`/api/status`、`/widget-data.json` 和 Android Widget 都消费同一份 JSON。Android 不解析 Excel，也不重新计算经营指标。

使用已下载的 Excel 生成网页/API 和离线文件：

```bash
./start-dashboard.sh \
  --input "/path/to/排课列表.xlsx" \
  --one-to-one-students 100 \
  --total-students 200 \
  --export-json ./widget-data.json
```

这是 V0.1 的旧服务端流程，不属于 Standalone Widget V0.2 的默认路径。V0.2 不启动网页服务器、不联网，只通过 Android App 导入电脑生成的 JSON 文件。旧流程说明见 [V0.1 产品化说明](docs/V0.1_PRODUCTIZATION.md)。

### 本地经营指标卡片（只读）

使用昨天已经下载的排课 Excel，不会触发下载：

```bash
./start-dashboard.sh --input "/path/to/排课列表.xlsx"
```

省略 `--input` 时会从 `~/Downloads` 和 `~/Desktop` 自动选择最近的 `排课列表_*` 文件。启动后终端会打印 Mac 本机地址和局域网 Android 地址；页面刷新只重新读取同一份输入。

## 历史服务端流程的数据安全说明

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
