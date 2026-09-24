package com.li281077304.eduops.widget

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

private val cardKeys = listOf(
    "monthly_produced_ks", "monthly_planned_ks", "monthly_lesson_count",
    "monthly_completed_lessons", "monthly_scheduled_lessons", "monthly_cancelled_lessons",
    "weekly_produced_ks", "weekly_planned_ks", "weekly_completed_lessons",
    "weekly_scheduled_lessons", "weekly_average_lessons", "one_to_one_produced_ks",
    "one_to_one_planned_ks", "class_produced_ks", "class_planned_ks", "teacher_count",
)

private fun contractJson(schema: Int = 2, cards: String? = null): String {
    val cardData = cards ?: cardKeys.mapIndexed { index, key ->
        val section = when (index) {
            in 0..5 -> "month"
            in 6..10 -> "week"
            else -> "structure"
        }
        """{"key":"$key","label":"Metric $index","value":$index,"unit":"KS","format":"number","section":"$section","availability":"available","definition":"synthetic fixture"}"""
    }.joinToString(",", "[", "]")
    return """{"schema_version":$schema,"dashboard":{"id":"fixture","name":"Fixture"},"updated_at":"2026-09-16T09:00:00+08:00","period":{"start":"2026-08-31","end":"2026-09-27","label":"Fixture period"},"source":{"file_name":"synthetic.xlsx","sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","record_count":1},"cards":$cardData,"sections":{"month":[${cardKeys.take(6).joinToString(",") { "\"$it\"" }}],"week":[${cardKeys.slice(6..10).joinToString(",") { "\"$it\"" }}],"structure":[${cardKeys.drop(11).joinToString(",") { "\"$it\"" }}]}}"""
}

class WidgetMetricsTest {
    @Test
    fun parsesContractV2WithoutRecalculatingMetrics() {
        val payload = WidgetPayload.fromDashboardJson(contractJson())

        assertEquals(2, payload.schemaVersion)
        assertEquals("Fixture", payload.dashboardName)
        assertEquals("0 KS", formatCard(payload.card("monthly_produced_ks")!!))
        assertEquals("15 KS", formatCard(payload.card("teacher_count")!!))
    }

    @Test
    fun rejectsUnsupportedSchemaAndIncompleteCards() {
        var rejected = false
        try {
            WidgetPayload.fromDashboardJson(contractJson(schema = 3))
        } catch (_: IllegalArgumentException) {
            rejected = true
        }
        assertTrue(rejected)

        rejected = false
        try {
            WidgetPayload.fromDashboardJson(contractJson(cards = "[]"))
        } catch (_: IllegalArgumentException) {
            rejected = true
        }
        assertTrue(rejected)
    }

    @Test
    fun rejectsLegacySchemaAndUnknownUnavailableCards() {
        var rejected = false
        try {
            WidgetPayload.fromDashboardJson(contractJson(schema = 1))
        } catch (_: IllegalArgumentException) {
            rejected = true
        }
        assertTrue(rejected)

        val unavailable = contractJson().replaceFirst(
            "\"availability\":\"available\"",
            "\"availability\":\"unavailable\"",
        )
        rejected = false
        try {
            WidgetPayload.fromDashboardJson(unavailable)
        } catch (_: IllegalArgumentException) {
            rejected = true
        }
        assertTrue(rejected)
    }
}
