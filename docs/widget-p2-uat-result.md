# Android Dashboard Widget P2 UAT

日期：2026-09-15

## 视觉参照与实现

本轮视觉参照采用 Android Developers 的 Jetpack Glance Widget 布局/响应式尺寸实践，以及 Material 3 的 shape/card 视觉语言：

- [Create an app widget with Glance](https://developer.android.com/develop/ui/compose/glance/create-app-widget)
- [Material 3 shape overview](https://m3.material.io/styles/shape/overview)

实现调整：

- 所有六张卡统一使用同一张 `widget_card_background.xml`，圆角 18dp。
- 外层容器使用统一的 28dp 圆角背景。
- 卡片之间使用 8dp 间距，外层使用 12dp padding，避免表格拼接感。
- 标签弱化、数值加粗；六张卡仍保持 2 列 × 3 行。

## 指标口径

- 经营课时统一显示 `KS`，不再显示 `H`、`Hours` 或“小时”。
- 一对一周平均：`oneToOneKs / oneToOneStudentCount / weeksInPeriod`。
- 全员周平均：`totalKs / totalStudentCount / weeksInPeriod`；分母独立包含全员，不使用教师数或一对一人数替代。
- 测试人工月明确为 `weeksInPeriod = 4`，没有把 `4` 散落在计算函数中。
- 平均课次保留“次”，不重新定义既有业务口径。
- 大小周卡只显示周总量：`大周 1300 KS`、`小周 700 KS`。
- 六张卡从 `testDashboardMetrics` 生成；测试数据可以写死，但周平均显示值通过统一计算函数产生。

测试数据中的关键结果：

| 案例 | 计算 | 结果 |
|---|---|---:|
| 4 周上 4 次，每次 3 KS | `12 / 1 / 4` | `3.0 KS` |
| 4 周上 2 次，每次 3 KS | `6 / 1 / 4` | `1.5 KS` |
| 一对一示例 | `1200 / 100 / 4` | `3.0 KS` |
| 全员示例 | `7680 / 200 / 4` | `9.6 KS` |

## Gate 结果

| Gate | 结果 | 证据 |
|---|---|---|
| A — APK 构建 | PASS | `./gradlew clean testDebugUnitTest :app:assembleDebug`：`BUILD SUCCESSFUL` |
| A — 安装到真实手机 | BLOCKED | `adb devices -l` 无连接设备；未执行安装 |
| B — 真实主屏视觉 | PENDING | 没有可用手机/模拟器，无法取得桌面截图进行人工验收 |
| C — KS 单位 | PASS | Widget 源码禁用词扫描通过；课时卡均使用 `KS` |
| D — 周平均计算 | PASS | Android unit tests 3 项通过，含 3.0 和 1.5 两个关键案例 |
| E — 六卡结构 | PASS | 源码静态检查确认仅有六张 `MetricCard`，顺序符合 UAT |

因此，本轮代码和 Machine Gate 已通过；完整 P2 UAT 尚未完成，待连接真实 Android 手机后补齐 Gate A 安装和 Gate B 人工视觉验收。

## APK 与命令

- APK：`android-widget/app/build/outputs/apk/debug/app-debug.apk`
- 绝对路径：`/Users/macos/Documents/Codex/2026-09-13/referenced-chatgpt-conversation-this-is-an/outputs/edu-ops-dashboard/android-widget/app/build/outputs/apk/debug/app-debug.apk`
- SHA-256：`0327c40c7490ae9b0fa207e2ae5cf98b5517bfe93d02b9c91b97a78645d3a949`
- 构建：

```bash
cd android-widget
ANDROID_SDK_ROOT=/tmp/android-sdk-widget-p0 ./gradlew clean testDebugUnitTest :app:assembleDebug
```

APK `apksigner verify --verbose` 通过，Android Manifest 包含 Widget receiver、provider metadata 和 `resizeMode="horizontal|vertical"`。

## 修改文件

- `android-widget/app/build.gradle.kts`
- `android-widget/app/src/main/kotlin/com/li281077304/eduops/widget/DashboardWidget.kt`
- `android-widget/app/src/main/kotlin/com/li281077304/eduops/widget/WidgetMetrics.kt`
- `android-widget/app/src/main/kotlin/com/li281077304/eduops/widget/MainActivity.kt`（未改动，仅列入 Widget 工程范围）
- `android-widget/app/src/test/kotlin/com/li281077304/eduops/widget/WidgetMetricsTest.kt`
- `android-widget/app/src/main/res/drawable/widget_card_background.xml`
- `android-widget/app/src/main/res/drawable/widget_surface_background.xml`
- `docs/widget-p2-uat-result.md`

本轮未删除或修改 Python 数据采集、指标计算代码，也未修改原有用户未提交的 Python 文件。
