# Weekly Report source inbox

把每周 WPS/TMS/CSV/XLS/XLSX 原始导出放入此目录（或通过
`edu-ops weekly-report run --source-root` 指向受控目录）。系统按文件内容、
表结构和可追溯来源识别输入，不要求修改脚本路径。原始文件不进入产品
Git；`SOURCE_MANIFEST.json` 记录其路径、周期、hash 和更新时间。
