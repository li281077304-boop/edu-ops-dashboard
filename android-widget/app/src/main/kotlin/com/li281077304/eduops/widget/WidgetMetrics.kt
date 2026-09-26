package com.li281077304.eduops.widget

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject
import java.net.URI

internal const val V2_SCHEMA_VERSION = 2

/** Fixed display order and the v2 contract's 16 metric keys. */
internal val V2_CARD_KEYS = listOf(
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
private val SMALL_CARD_KEYS = listOf(
    "monthly_produced_ks", "monthly_planned_ks", "weekly_produced_ks",
    "weekly_planned_ks", "weekly_average_lessons", "teacher_count",
)
private val MEDIUM_CARD_KEYS = SMALL_CARD_KEYS + listOf(
    "monthly_lesson_count", "monthly_completed_lessons", "monthly_scheduled_lessons",
    "monthly_cancelled_lessons",
)
private val V2_SECTIONS = linkedMapOf(
    "month" to V2_CARD_KEYS.subList(0, 6),
    "week" to V2_CARD_KEYS.subList(6, 11),
    "structure" to V2_CARD_KEYS.subList(11, 16),
)

private data class CardTemplate(
    val key: String, val label: String, val unit: String, val format: String,
    val section: String, val definition: String,
)

private val CARD_TEMPLATES = listOf(
    CardTemplate("monthly_produced_ks", "月度已生产", "KS", "number", "month", "人工月内已上课记录按实到人数计算。"),
    CardTemplate("monthly_planned_ks", "月度预排", "KS", "number", "month", "人工月内按现有预排口径计算。"),
    CardTemplate("monthly_lesson_count", "月度总课次", "课次", "number", "month", "已上课与未上课课次之和，不含取消课。"),
    CardTemplate("monthly_completed_lessons", "月度已上课", "课次", "number", "month", "数据截止日前已上课课次。"),
    CardTemplate("monthly_scheduled_lessons", "月度未上课", "课次", "number", "month", "状态为未上课或已排的课次。"),
    CardTemplate("monthly_cancelled_lessons", "月度已取消", "课次", "number", "month", "取消或作废课次，单独统计。"),
    CardTemplate("weekly_produced_ks", "本周已生产", "KS", "number", "week", "本周一至数据截止日已上课记录按实到计算。"),
    CardTemplate("weekly_planned_ks", "本周预排", "KS", "number", "week", "当前完整自然周按预排口径计算。"),
    CardTemplate("weekly_completed_lessons", "本周已上课", "课次", "number", "week", "本周一至数据截止日已上课课次。"),
    CardTemplate("weekly_scheduled_lessons", "本周未上课", "课次", "number", "week", "当前自然周未上课或已排课次。"),
    CardTemplate("weekly_average_lessons", "本周平均课次", "课次/教师", "number", "week", "沿用现有累计排课课次除以教师数口径。"),
    CardTemplate("one_to_one_produced_ks", "一对一已生产", "KS", "number", "structure", "一对一已上课记录按实到计算。"),
    CardTemplate("one_to_one_planned_ks", "一对一预排", "KS", "number", "structure", "一对一按现有预排口径计算。"),
    CardTemplate("class_produced_ks", "班课已生产", "KS", "number", "structure", "非一对一已上课记录按实到计算。"),
    CardTemplate("class_planned_ks", "班课预排", "KS", "number", "structure", "非一对一按现有预排口径计算。"),
    CardTemplate("teacher_count", "教师数", "人", "number", "structure", "人工月涉及教师去重数。"),
)
private val templateByKey = CARD_TEMPLATES.associateBy { it.key }

data class WidgetCard(
    val key: String, val label: String, val value: String?, val unit: String, val format: String,
    val section: String, val availability: String, val definition: String, val reason: String? = null,
) {
    val isDisplayable: Boolean get() = availability == "available" && value != null
}

data class WidgetPayload(
    val schemaVersion: Int,
    val dashboardId: String,
    val dashboardName: String,
    val updatedAt: String,
    val periodStart: String,
    val periodEnd: String,
    val periodLabel: String,
    val dataStatus: String,
    val cards: List<WidgetCard>,
    internal val migratedFromV1: Boolean = false,
    internal val rawContractJson: String? = null,
) {
    fun card(key: String): WidgetCard? = cards.firstOrNull { it.key == key }
    fun visibleCards(limit: Int): List<WidgetCard> {
        val keys = when (limit) {
            6 -> SMALL_CARD_KEYS
            10 -> MEDIUM_CARD_KEYS
            else -> V2_CARD_KEYS
        }
        val byKey = cards.associateBy { it.key }
        return keys.mapNotNull(byKey::get).filter { it.isDisplayable }
    }

    fun toCacheJson(): String {
        return rawContractJson ?: error("缓存前必须先验证并规范化 Contract v2")
    }

    companion object {
        /** Display-only parser: Android validates input but never derives metrics. */
        fun fromDashboardJson(json: String): WidgetPayload {
            val root = JSONObject(json)
            return when (root.requireInt("schema_version")) {
                V2_SCHEMA_VERSION -> parseV2(root)
                1 -> migrateV1(root)
                else -> throw IllegalArgumentException("不支持的 Dashboard 数据版本")
            }
        }

        private fun parseV2(root: JSONObject): WidgetPayload {
            val common = parseCommon(root, V2_SCHEMA_VERSION)
            validatePeriod(root.requireObject("period"))
            validateSource(root.requireObject("source"))
            val cardsJson = root.requireArray("cards")
            require(cardsJson.length() == V2_CARD_KEYS.size) { "Dashboard 必须包含 16 张指标卡" }
            val cardsByKey = mutableMapOf<String, WidgetCard>()
            for (index in 0 until cardsJson.length()) {
                val item = cardsJson.requireObject(index, "cards[$index]")
                val card = WidgetCard(
                    key = item.requireText("key"), label = item.requireText("label"),
                    value = item.optionalStringOrNull("value"), unit = item.requireText("unit"),
                    format = item.requireText("format"), section = item.requireText("section"),
                    availability = item.requireText("availability"), definition = item.requireText("definition"),
                    reason = item.optionalStringOrNull("reason"),
                )
                require(card.availability in setOf("available", "unavailable")) { "cards[$index].availability 无效" }
                require((card.availability == "available") == (card.value != null)) { "cards[$index] 的 availability 与 value 不一致" }
                require(card.section == sectionFor(card.key)) { "cards[$index].section 无效" }
                require(card.format == if (card.value == null) "unavailable" else "number") { "cards[$index].format 无效" }
                require(card.value != null || !card.reason.isNullOrBlank()) { "cards[$index] 缺少不可用原因" }
                require(cardsByKey.put(card.key, card) == null) { "Dashboard 指标 key 重复" }
            }
            require(cardsByKey.keys.toList() == V2_CARD_KEYS) { "Dashboard 指标 key 不完整、顺序无效或未知" }
            validateSections(root.requireObject("sections"), V2_CARD_KEYS)
            return common.copy(cards = V2_CARD_KEYS.map { cardsByKey.getValue(it) }, rawContractJson = root.toString())
        }

        /** V1 is accepted only at import/cache boundaries, then persisted as full v2. */
        private fun migrateV1(root: JSONObject): WidgetPayload {
            val common = parseCommon(root, 1)
            val oldValues = mutableMapOf<String, String>()
            val v1Cards = root.requireArray("cards")
            for (index in 0 until v1Cards.length()) {
                val card = v1Cards.requireObject(index, "cards[$index]")
                card.optionalStringOrNull("value")?.let { oldValues[card.requireText("key")] = it }
            }
            val values = mapOf(
                "monthly_produced_ks" to oldValues["monthly_produced_ks"],
                "monthly_planned_ks" to oldValues["monthly_planned_ks"],
                "weekly_average_lessons" to (oldValues["weekly_average_lessons"] ?: oldValues["average_lessons"]),
                "teacher_count" to root.optJSONObject("quality")?.optInt("teacher_count")
                    ?.takeIf { root.optJSONObject("quality")?.has("teacher_count") == true }?.toString(),
            )
            val cards = V2_CARD_KEYS.map { key ->
                val template = templateByKey.getValue(key)
                val value = values[key]
                WidgetCard(
                    key, template.label, value, template.unit,
                    if (value == null) "unavailable" else "number",
                    template.section,
                    if (value == null) "unavailable" else "available",
                    template.definition,
                    if (value == null) "旧版文件没有提供该项数据。" else null,
                )
            }
            val period = root.requireObject("period")
            val dateStart = period.requireText("start")
            val dateEnd = period.requireText("end")
            val payload = JSONObject()
                .put("schema_version", V2_SCHEMA_VERSION)
                .put("data_status", common.dataStatus)
                .put("dashboard", JSONObject().put("id", common.dashboardId).put("name", common.dashboardName))
                .put("updated_at", common.updatedAt)
                .put("period", JSONObject()
                    .put("manual_month", period.optInt("manual_month", 0))
                    .put("weeks", period.optInt("weeks", 0))
                    .put("start", dateStart).put("end", dateEnd)
                    .put("label", common.periodLabel).put("data_cutoff", dateEnd)
                    .put("current_week_start", dateStart).put("current_week_end", dateEnd))
                .put("source", JSONObject()
                    .put("filename", "legacy-v1")
                    .put("sha256", "0".repeat(64))
                    .put("size_bytes", 0).put("format", "legacy").put("row_count", 0)
                    .put("date_coverage", JSONObject().put("start", dateStart).put("end", dateEnd))
                    .put("duplicate_rows", 0))
                .put("cards", cards.toJsonArray())
                .put("sections", sectionsJson())
                .put("migration", JSONObject().put("from_schema_version", 1))
            val v2 = parseV2(payload)
            return v2.copy(migratedFromV1 = true)
        }

        private fun parseCommon(root: JSONObject, expectedVersion: Int): WidgetPayload {
            require(root.requireInt("schema_version") == expectedVersion) { "schema_version 无效" }
            val dashboard = root.requireObject("dashboard")
            val period = root.requireObject("period")
            return WidgetPayload(expectedVersion, dashboard.requireText("id"), dashboard.requireText("name"),
                root.requireText("updated_at"), period.requireText("start"), period.requireText("end"),
                period.requireText("label"), root.optString("data_status", "live").ifBlank { "live" }, emptyList())
        }

        private fun validatePeriod(period: JSONObject) {
            period.requireInt("manual_month")
            period.requireInt("weeks")
            listOf("start", "end", "label", "data_cutoff", "current_week_start", "current_week_end")
                .forEach(period::requireText)
        }

        private fun validateSource(source: JSONObject) {
            source.requireText("filename")
            require(Regex("[0-9a-fA-F]{64}").matches(source.requireText("sha256"))) { "source.sha256 无效" }
            require(source.requireInt("size_bytes") >= 0) { "source.size_bytes 无效" }
            source.requireText("format")
            require(source.requireInt("row_count") >= 0) { "source.row_count 无效" }
            require(source.requireInt("duplicate_rows") >= 0) { "source.duplicate_rows 无效" }
            val coverage = source.requireObject("date_coverage")
            coverage.requireText("start"); coverage.requireText("end")
        }

        private fun validateSections(sections: JSONObject, keys: List<String>) {
            V2_SECTIONS.forEach { (name, expected) ->
                val values = sections.requireArray(name)
                require((0 until values.length()).map { values.getString(it) } == expected) {
                    "sections.$name 与指标分组不一致"
                }
            }
            require(sections.length() == V2_SECTIONS.size && keys.size == V2_CARD_KEYS.size) {
                "Dashboard sections 不完整"
            }
        }
    }
}

private fun JSONObject.requireText(name: String): String {
    val value = opt(name)
    require(value is String && value.trim().isNotEmpty()) { "$name 必须是非空文本" }
    return value.trim()
}
private fun JSONObject.requireInt(name: String): Int {
    val value = opt(name)
    require(value is Number && value.toDouble() % 1.0 == 0.0) { "$name 必须是整数" }
    return value.toInt()
}
private fun JSONObject.requireObject(name: String): JSONObject {
    val value = opt(name); require(value is JSONObject) { "$name 必须是对象" }; return value
}
private fun JSONObject.requireArray(name: String): JSONArray {
    val value = opt(name); require(value is JSONArray) { "$name 必须是数组" }; return value
}
private fun JSONArray.requireObject(index: Int, field: String): JSONObject {
    val value = opt(index); require(value is JSONObject) { "$field 必须是对象" }; return value
}
private fun JSONObject.optionalStringOrNull(name: String): String? {
    val value = opt(name)
    if (value == null || value == JSONObject.NULL) return null
    require(value is String) { "$name 必须是字符串或 null" }
    return value
}
private fun List<WidgetCard>.toJsonArray(): JSONArray = JSONArray().also { array ->
    forEach { card -> array.put(JSONObject()
        .put("key", card.key).put("label", card.label).put("value", card.value ?: JSONObject.NULL)
        .put("unit", card.unit).put("format", card.format).put("section", card.section)
        .put("availability", card.availability).put("definition", card.definition)
        .also { if (card.reason != null) it.put("reason", card.reason) }) }
}

private fun sectionsJson(): JSONObject = JSONObject().also { sections ->
    V2_SECTIONS.forEach { (name, keys) -> sections.put(name, JSONArray(keys)) }
}

private fun sectionFor(key: String): String = when (key) {
    in V2_SECTIONS.getValue("month") -> "month"
    in V2_SECTIONS.getValue("week") -> "week"
    else -> "structure"
}

internal object DashboardConfig {
    private const val PREFS = "dashboard_widget"
    private const val ENDPOINT = "advanced_endpoint"
    private const val PAYLOAD = "last_payload"
    fun preferences(context: Context): SharedPreferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    fun endpoint(context: Context): String = preferences(context).getString(ENDPOINT, "") ?: ""
    /** Stored for an explicitly enabled future integration; V0.2 never calls it. */
    fun setEndpoint(context: Context, endpoint: String) {
        preferences(context).edit().putString(ENDPOINT, requireValidEndpoint(endpoint)).commit()
    }
    fun requireValidEndpoint(endpoint: String): String {
        val value = endpoint.trim(); val uri = runCatching { URI(value) }.getOrNull()
        require(uri != null && uri.host != null && uri.scheme in setOf("http", "https")) { "地址必须是完整的 http(s) URL" }
        return value
    }
    fun cachedPayload(context: Context): WidgetPayload? {
        val json = preferences(context).getString(PAYLOAD, null) ?: return null
        return runCatching { WidgetPayload.fromDashboardJson(json) }.getOrNull()?.also { if (it.migratedFromV1) saveValidatedPayload(context, it) }
    }
    fun samplePayload(context: Context): WidgetPayload = context.assets.open("widget-data.json").bufferedReader().use { WidgetPayload.fromDashboardJson(it.readText()) }
    fun currentPayload(context: Context): WidgetPayload = cachedPayload(context) ?: samplePayload(context)
    /** Parse before commit: a bad import cannot replace an earlier good cache. */
    fun saveImportedPayload(context: Context, json: String): WidgetPayload {
        val payload = WidgetPayload.fromDashboardJson(json); saveValidatedPayload(context, payload); return payload
    }
    private fun saveValidatedPayload(context: Context, payload: WidgetPayload) {
        check(preferences(context).edit().putString(PAYLOAD, payload.toCacheJson()).commit()) { "无法保存 Dashboard 数据" }
    }
}

internal fun formatCard(card: WidgetCard): String {
    val value = card.value ?: "数据不可用"
    if (card.unit.isBlank()) return value
    return value.lines().joinToString("\n") { if (it.isBlank() || it.endsWith(card.unit)) it else "$it ${card.unit}" }
}
internal fun visibleCardLimitFor(widthDp: Float): Int = when {
    widthDp < 240f -> SMALL_CARD_KEYS.size
    widthDp < 360f -> MEDIUM_CARD_KEYS.size
    else -> V2_CARD_KEYS.size
}
