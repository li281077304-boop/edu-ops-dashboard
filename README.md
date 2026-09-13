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
