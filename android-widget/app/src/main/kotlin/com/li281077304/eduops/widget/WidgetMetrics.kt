package com.li281077304.eduops.widget

import org.json.JSONObject

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

const val DASHBOARD_API_URL = "http://10.0.2.2:8765/api/status"
private const val SCHEMA_VERSION = 1

internal fun formatCard(card: WidgetCard): String =
    if (card.unit.isBlank()) card.value else "${card.value} ${card.unit}"
