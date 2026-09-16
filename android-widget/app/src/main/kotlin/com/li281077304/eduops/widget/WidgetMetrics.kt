package com.li281077304.eduops.widget

import android.content.Context
import android.content.SharedPreferences
import java.net.URI
import org.json.JSONObject

internal object DashboardConfig {
    const val DEFAULT_ENDPOINT = "http://10.0.2.2:8787/api/status"
    private const val PREFS = "dashboard_widget"
    private const val ENDPOINT = "endpoint"
    private const val PAYLOAD = "last_payload"

    fun preferences(context: Context): SharedPreferences =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun endpoint(context: Context): String =
        preferences(context).getString(ENDPOINT, DEFAULT_ENDPOINT) ?: DEFAULT_ENDPOINT

    fun setEndpoint(context: Context, endpoint: String) {
        requireValidEndpoint(endpoint)
        preferences(context).edit().putString(ENDPOINT, endpoint.trim()).apply()
    }

    fun requireValidEndpoint(endpoint: String): String {
        val value = endpoint.trim()
        val uri = runCatching { URI(value) }.getOrNull()
        require(
            uri != null && uri.host != null && uri.path.orEmpty().isNotBlank() &&
                (uri.scheme == "http" || uri.scheme == "https"),
        ) {
            "Dashboard 地址必须是完整的 http(s) URL"
        }
        return value
    }

    fun cachedPayload(context: Context): WidgetPayload? =
        preferences(context).getString(PAYLOAD, null)?.let { runCatching { WidgetPayload.fromDashboardJson(it) }.getOrNull() }

    fun savePayload(context: Context, json: String) {
        preferences(context).edit().putString(PAYLOAD, json).apply()
    }
}

/** The versioned, normalized payload exposed by Dashboard for non-browser clients. */
data class WidgetCard(
    val key: String,
    val label: String,
    val value: String,
    val unit: String,
)

data class WidgetPayload(
    val schemaVersion: Int,
    val updatedAt: String,
    val periodStart: String,
    val periodEnd: String,
    val manualMonth: Int,
    val weeks: Int,
    val cards: List<WidgetCard>,
) {
    fun card(key: String): WidgetCard? = cards.firstOrNull { it.key == key }

    companion object {
        fun fromDashboardJson(json: String): WidgetPayload {
            val widget = JSONObject(json).getJSONObject("widget")
            val period = widget.getJSONObject("period")
            val cardsJson = widget.getJSONArray("cards")
            val cards = buildList(cardsJson.length()) {
                for (index in 0 until cardsJson.length()) {
                    val card = cardsJson.getJSONObject(index)
                    add(
                        WidgetCard(
                            key = card.getString("key"),
                            label = card.getString("label"),
                            value = card.getString("value"),
                            unit = card.getString("unit"),
                        ),
                    )
                }
            }
            require(widget.getInt("schema_version") == SCHEMA_VERSION) {
                "Unsupported Dashboard widget schema"
            }
            require(cards.isNotEmpty()) { "Dashboard widget payload has no cards" }
            return WidgetPayload(
                schemaVersion = widget.getInt("schema_version"),
                updatedAt = widget.getString("updated_at"),
                periodStart = period.getString("start"),
                periodEnd = period.getString("end"),
                manualMonth = period.getInt("manual_month"),
                weeks = period.getInt("weeks"),
                cards = cards,
            )
        }
    }
}

private const val SCHEMA_VERSION = 1

internal fun formatCard(card: WidgetCard): String =
    if (card.unit.isBlank()) card.value else "${card.value} ${card.unit}"
