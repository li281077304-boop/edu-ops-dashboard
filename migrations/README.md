# 数据库迁移

`001_metrics.sql` 只定义聚合指标和预排快照，不存学生、老师或原始课表明细。使用 Compose 新建 PostgreSQL volume 时，初始化脚本会自动连接 `edu_ops` 并按顺序执行两份迁移；手工部署时再执行下面的步骤。

手工部署前应先创建两个逻辑数据库：

- `metabase_app`：Metabase 自己的配置库；
- `edu_ops`：本项目的指标库，执行本目录的迁移。

部署凭据只从运行环境注入，不能写进迁移文件。已有 PostgreSQL volume 不会重复执行 `/docker-entrypoint-initdb.d`，升级迁移必须按运维流程单独执行。
