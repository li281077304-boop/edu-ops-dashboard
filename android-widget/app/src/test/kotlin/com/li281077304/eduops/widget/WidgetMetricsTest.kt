package com.li281077304.eduops.widget

import org.junit.Assert.assertEquals
import org.junit.Test

class WidgetMetricsTest {
    @Test
    fun defaultEndpointMatchesDashboardPortAndWidgetPath() {
        assertEquals("http://10.0.2.2:8787/api/status", DashboardConfig.DEFAULT_ENDPOINT)
    }

    @Test
    fun endpointValidationAllowsEmulatorLanAndHttpsAddresses() {
        assertEquals(
            "http://192.168.1.20:8787/api/status",
            DashboardConfig.requireValidEndpoint(" http://192.168.1.20:8787/api/status "),
        )
        assertEquals(
            "https://dashboard.example/api/status",
            DashboardConfig.requireValidEndpoint("https://dashboard.example/api/status"),
        )
    }

    @Test
    fun parsesTheVersionedDashboardWidgetPayload() {
        val payload = WidgetPayload.fromDashboardJson(
            """{"widget":{"schema_version":1,"updated_at":"2026-09-15T15:30:00+08:00","period":{"start":"2026-08-31","end":"2026-09-27","manual_month":9,"weeks":4},"cards":[{"key":"production_hours","label":"生产课时","value":"6","unit":"课时"},{"key":"teacher_count","label":"参与教师数","value":"2","unit":"人"}]}}""",
        )

        assertEquals(1, payload.schemaVersion)
        assertEquals("2026-08-31", payload.periodStart)
        assertEquals("6 课时", formatCard(payload.card("production_hours")!!))
        assertEquals("2 人", formatCard(payload.card("teacher_count")!!))
    }
}
