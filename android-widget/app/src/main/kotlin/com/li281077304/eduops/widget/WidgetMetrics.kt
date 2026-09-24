package com.li281077304.eduops.widget

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONObject

private const val SCHEMA_VERSION = 2
private val CARD_KEYS = listOf(
    "monthly_produced_ks",
    "monthly_planned_ks",
    "monthly_lesson_count",
    "monthly_completed_lessons",
    "monthly_scheduled_lessons",
    "monthly_cancelled_lessons",
    "weekly_produced_ks",
    "weekly_planned_ks",
    "weekly_completed_lessons",
    "weekly_scheduled_lessons",
    "weekly_average_lessons",
    "one_to_one_produced_ks",
    "one_to_one_planned_ks",
    "class_produced_ks",
    "class_planned_ks",
    "teacher_count",
)
private val SECTIONS = listOf("month", "week", "structure")

data class WidgetCard(
    val key: String,
    val label: String,
    val value: String,
    val unit: String,
    val format: String,
    val section: String,
    val availability: String,
    val definition: String,
)

data class WidgetPayload(
    val schemaVersion: Int,
    val dashboardId: String,
    val dashboardName: String,
    val updatedAt: String,
    val periodStart: String,
    val periodEnd: String,
    val periodLabel: String,
    val cards: List<WidgetCard>,
) {
    fun card(key: String): WidgetCard? = cards.firstOrNull { it.key == key }

    companion object {
        fun fromDashboardJson(json: String): WidgetPayload {
            val root = JSONObject(json)
            require(root.getInt("schema_version") == SCHEMA_VERSION) {
                "不支持的 Dashboard 数据版本"
            }
            val dashboard = root.getJSONObject("dashboard")
            val period = root.getJSONObject("period")
            val source = root.getJSONObject("source")
            require(dashboard.getString("id").isNotBlank() && dashboard.getString("name").isNotBlank()) {
                "Dashboard 标识缺失"
            }
            require(root.getString("updated_at").isNotBlank()) { "更新时间缺失" }
            require(period.getString("start").isNotBlank() && period.getString("end").isNotBlank()) {
                "统计周期缺失"
            }
            require(period.getString("label").isNotBlank()) { "统计周期说明缺失" }
            require(source.getString("file_name").isNotBlank()) { "来源文件名缺失" }
            require(Regex("[0-9a-f]{64}").matches(source.getString("sha256"))) { "来源指纹无效" }
            val recordCount = source.get("record_count")
            require(recordCount is Number && recordCount.toInt() > 0) { "来源记录数无效" }
            val cardsJson = root.getJSONArray("cards")
            require(cardsJson.length() == CARD_KEYS.size) { "Dashboard 必须包含十六张卡" }
            val cards = buildList(cardsJson.length()) {
                for (index in 0 until cardsJson.length()) {
                    val card = cardsJson.getJSONObject(index)
                    require(card.getString("key") == CARD_KEYS[index]) { "Dashboard 卡片顺序无效" }
                    val format = card.getString("format")
                    require(format == "number") { "卡片格式无效" }
                    require(card.getString("availability") == "available") { "卡片不可用" }
                    require(card.getString("label").isNotBlank() && card.getString("definition").isNotBlank()) {
                        "Dashboard 卡片说明缺失"
                    }
                    require(card.getString("unit").isNotBlank()) { "Dashboard 卡片单位缺失" }
                    val number = card.get("value")
                    require(number is Number && number.toDouble().isFinite()) { "Dashboard 卡片值无效" }
                    add(
                        WidgetCard(
                            key = card.getString("key"),
                            label = card.getString("label"),
                            value = card.get("value").toString(),
                            unit = card.optString("unit"),
                            format = format,
                            section = card.getString("section"),
                            availability = card.getString("availability"),
                            definition = card.getString("definition"),
                        ),
                    )
                }
            }
            val sections = root.getJSONObject("sections")
            require(sections.keys().asSequence().toSet() == SECTIONS.toSet()) { "Dashboard 分区字段无效" }
            require(SECTIONS.all { sections.has(it) }) { "Dashboard 分区不完整" }
            val groupedKeys = SECTIONS.flatMap { section ->
                val keys = sections.getJSONArray(section)
                (0 until keys.length()).map { keys.getString(it) }
            }
            require(groupedKeys == cards.map { it.key }) { "Dashboard 分区与卡片不一致" }
            val cardSection = cards.associate { it.key to it.section }
            val sectionMatches = SECTIONS.all { section ->
                val keys = sections.getJSONArray(section)
                (0 until keys.length()).all { cardSection[keys.getString(it)] == section }
            }
            require(sectionMatches && cards.all { it.section in SECTIONS }) {
                "Dashboard 卡片元数据不完整"
            }
            return WidgetPayload(
                schemaVersion = root.getInt("schema_version"),
                dashboardId = dashboard.getString("id"),
                dashboardName = dashboard.getString("name"),
                updatedAt = root.getString("updated_at"),
                periodStart = period.getString("start"),
                periodEnd = period.getString("end"),
                periodLabel = period.getString("label"),
                cards = cards,
            )
        }
    }
}

internal object DashboardConfig {
    private const val PREFS = "dashboard_widget"
    private const val PAYLOAD = "last_payload"

    fun preferences(context: Context): SharedPreferences =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun cachedJson(context: Context): String? = preferences(context).getString(PAYLOAD, null)

    fun cachedPayload(context: Context): WidgetPayload? =
        cachedJson(context)?.let { runCatching { WidgetPayload.fromDashboardJson(it) }.getOrNull() }

    fun currentPayload(context: Context): WidgetPayload? = cachedPayload(context)

    /** SharedPreferences commit makes the new validated payload visible as one completed write. */
    fun savePayload(context: Context, json: String) {
        WidgetPayload.fromDashboardJson(json)
        check(preferences(context).edit().putString(PAYLOAD, json).commit()) {
            "无法保存 Dashboard 数据"
        }
    }
}

internal fun formatCard(card: WidgetCard): String {
    if (card.unit.isBlank()) return card.value
    return card.value.lines().joinToString("\n") { line ->
        if (line.isBlank() || line.endsWith(card.unit)) line else "$line ${card.unit}"
    }
}
