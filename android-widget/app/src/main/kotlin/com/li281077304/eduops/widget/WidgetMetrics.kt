package com.li281077304.eduops.widget

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONObject
import java.net.URI

private const val SCHEMA_VERSION = 1
private val CARD_KEYS = listOf(
    "monthly_produced_ks",
    "monthly_planned_ks",
    "one_to_one_weekly_average_ks",
    "total_weekly_average_ks",
    "average_lessons",
    "big_small_week_ks",
)

data class WidgetCard(
    val key: String,
    val label: String,
    val value: String,
    val unit: String,
    val format: String,
)

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
            val cardsJson = root.getJSONArray("cards")
            require(cardsJson.length() == CARD_KEYS.size) { "Dashboard 必须包含六张卡" }
            val cards = buildList(cardsJson.length()) {
                for (index in 0 until cardsJson.length()) {
                    val card = cardsJson.getJSONObject(index)
                    require(card.getString("key") == CARD_KEYS[index]) { "Dashboard 卡片顺序无效" }
                    val format = card.getString("format")
                    require(format in setOf("number", "text", "unavailable")) { "卡片格式无效" }
                    add(
                        WidgetCard(
                            key = card.getString("key"),
                            label = card.getString("label"),
                            value = card.getString("value"),
                            unit = card.optString("unit"),
                            format = format,
                        ),
                    )
                }
            }
            return WidgetPayload(
                schemaVersion = root.getInt("schema_version"),
                dashboardId = dashboard.getString("id"),
                dashboardName = dashboard.getString("name"),
                updatedAt = root.getString("updated_at"),
                periodStart = period.getString("start"),
                periodEnd = period.getString("end"),
                periodLabel = period.getString("label"),
                dataStatus = root.optString("data_status", "live"),
                cards = cards,
            )
        }
    }
}

internal object DashboardConfig {
    const val DEFAULT_ENDPOINT = "http://10.0.2.2:8787/widget-data.json"
    private const val PREFS = "dashboard_widget"
    private const val ENDPOINT = "endpoint"
    private const val DASHBOARD_ID = "dashboard_id"
    private const val PAYLOAD = "last_payload"

    fun preferences(context: Context): SharedPreferences =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun endpoint(context: Context): String =
        preferences(context).getString(ENDPOINT, DEFAULT_ENDPOINT) ?: DEFAULT_ENDPOINT

    fun dashboardId(context: Context): String =
        preferences(context).getString(DASHBOARD_ID, "xc2") ?: "xc2"

    fun setSettings(context: Context, endpoint: String, dashboardId: String) {
        requireValidEndpoint(endpoint)
        require(dashboardId.trim().isNotEmpty()) { "Dashboard ID 不能为空" }
        preferences(context).edit()
            .putString(ENDPOINT, endpoint.trim())
            .putString(DASHBOARD_ID, dashboardId.trim())
            .commit()
    }

    fun requireValidEndpoint(endpoint: String): String {
        val value = endpoint.trim()
        val uri = runCatching { URI(value) }.getOrNull()
        require(
            uri != null && uri.host != null && uri.path.orEmpty().isNotBlank() &&
                (uri.scheme == "http" || uri.scheme == "https"),
        ) { "Dashboard 地址必须是完整的 http(s) URL" }
        return value
    }

    fun cachedJson(context: Context): String? = preferences(context).getString(PAYLOAD, null)

    fun cachedPayload(context: Context): WidgetPayload? =
        cachedJson(context)?.let { runCatching { WidgetPayload.fromDashboardJson(it) }.getOrNull() }

    fun samplePayload(context: Context): WidgetPayload =
        context.assets.open("widget-data.json").bufferedReader().use {
            WidgetPayload.fromDashboardJson(it.readText())
        }

    fun currentPayload(context: Context): WidgetPayload = cachedPayload(context) ?: samplePayload(context)

    fun isSample(context: Context): Boolean =
        (cachedPayload(context)?.dataStatus ?: "sample") == "sample"

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
