package com.li281077304.eduops.widget

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

private fun contractJson(schema: Int = 1, cards: String = """[
    {"key":"monthly_produced_ks","label":"月度已生产","value":"8420","unit":"KS","format":"number"},
    {"key":"monthly_planned_ks","label":"月度预排","value":"10680","unit":"KS","format":"number"},
    {"key":"one_to_one_weekly_average_ks","label":"一对一周平均","value":"3","unit":"KS / 人 / 周","format":"number"},
    {"key":"total_weekly_average_ks","label":"全员周平均","value":"9.6","unit":"KS / 人 / 周","format":"number"},
    {"key":"average_lessons","label":"平均课次","value":"12.4","unit":"次 / 教师","format":"number"},
    {"key":"big_small_week_ks","label":"大小周课时","value":"大周 1300\n小周 700","unit":"KS","format":"text"}
]""") = """{"schema_version":$schema,"data_status":"live","dashboard":{"id":"xc2","name":"二校经营看板"},"updated_at":"2026-09-16T09:00:00+08:00","period":{"start":"2026-08-31","end":"2026-09-27","label":"人工月9 · 2026-08-31 ～ 2026-09-27"},"cards":$cards}"""

class WidgetMetricsTest {
    @Test
    fun parsesTheVersionedContractWithoutRecalculatingMetrics() {
        val payload = WidgetPayload.fromDashboardJson(contractJson())

        assertEquals(1, payload.schemaVersion)
        assertEquals("二校经营看板", payload.dashboardName)
        assertEquals("3 KS / 人 / 周", formatCard(payload.card("one_to_one_weekly_average_ks")!!))
        assertEquals("大周 1300 KS\n小周 700 KS", formatCard(payload.card("big_small_week_ks")!!))
    }

    @Test
    fun rejectsUnsupportedSchemaAndIncompleteCards() {
        var rejected = false
        try {
            WidgetPayload.fromDashboardJson(contractJson(schema = 2))
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
    fun endpointValidationIsExplicitAndTrimmed() {
        assertEquals(
            "https://dashboard.example/widget-data.json",
            DashboardConfig.requireValidEndpoint(" https://dashboard.example/widget-data.json "),
        )
        var rejected = false
        try {
            DashboardConfig.requireValidEndpoint("dashboard.example")
        } catch (_: IllegalArgumentException) {
            rejected = true
        }
        assertTrue(rejected)
    }
}
