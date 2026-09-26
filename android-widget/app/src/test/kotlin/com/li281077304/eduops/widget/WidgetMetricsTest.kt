package com.li281077304.eduops.widget

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

private fun v2Json(unavailableAfter: Int = Int.MAX_VALUE): String {
    val cards = JSONArray()
    V2_CARD_KEYS.forEachIndexed { index, key ->
        val available = index < unavailableAfter
        val section = when (index) { in 0..5 -> "month"; in 6..10 -> "week"; else -> "structure" }
        cards.put(JSONObject().put("key", key).put("label", "标签 $index")
            .put("value", if (available) "$index" else JSONObject.NULL)
            .put("unit", "单位").put("format", if (available) "number" else "unavailable").put("section", section)
            .put("availability", if (available) "available" else "unavailable").put("definition", "口径 $index")
            .also { if (!available) it.put("reason", "暂无可用数据") })
    }
    val sections = JSONObject()
        .put("month", JSONArray(V2_CARD_KEYS.subList(0, 6)))
        .put("week", JSONArray(V2_CARD_KEYS.subList(6, 11)))
        .put("structure", JSONArray(V2_CARD_KEYS.subList(11, 16)))
    return JSONObject().put("schema_version", 2).put("data_status", "live")
        .put("dashboard", JSONObject().put("id", "xc2").put("name", "二校经营看板"))
        .put("updated_at", "2026-09-24T08:00:00+08:00")
        .put("period", JSONObject().put("manual_month", 9).put("weeks", 4)
            .put("start", "2026-09-01").put("end", "2026-09-30").put("label", "人工月9")
            .put("data_cutoff", "2026-09-24").put("current_week_start", "2026-09-21")
            .put("current_week_end", "2026-09-27"))
        .put("source", JSONObject().put("filename", "sanitized-schedule.xlsx").put("sha256", "0".repeat(64))
            .put("size_bytes", 100).put("format", "xlsx").put("row_count", 16).put("duplicate_rows", 0)
            .put("date_coverage", JSONObject().put("start", "2026-09-01").put("end", "2026-09-24")))
        .put("cards", cards).put("sections", sections).toString()
}

private fun v1Json(): String = """{
  "schema_version": 1, "dashboard": {"id":"xc2","name":"旧看板"}, "updated_at":"2026-09-24T08:00:00+08:00",
  "period":{"start":"2026-09-01","end":"2026-09-30","label":"人工月9"}, "quality":{"teacher_count":12}, "cards":[
    {"key":"monthly_produced_ks","value":"100"}, {"key":"monthly_planned_ks","value":"120"},
    {"key":"average_lessons","value":"8.5"},
    {"key":"big_small_week_ks","value":"不应迁移"}
  ]
}"""

class WidgetMetricsTest {
    @Test
    fun responsiveSizesOnlyUseAvailableValuesAtSixTenAndSixteenLimits() {
        val complete = WidgetPayload.fromDashboardJson(v2Json())
        assertEquals(6, complete.visibleCards(visibleCardLimitFor(180f)).size)
        assertEquals(10, complete.visibleCards(visibleCardLimitFor(280f)).size)
        assertEquals(16, complete.visibleCards(visibleCardLimitFor(420f)).size)

        val partial = WidgetPayload.fromDashboardJson(v2Json(unavailableAfter = 12))
        assertEquals(12, partial.visibleCards(visibleCardLimitFor(420f)).size)
    }

    @Test
    fun migratesV1ValuesWithoutInventingMissingMetricsAndWritesV2Cache() {
        val payload = WidgetPayload.fromDashboardJson(v1Json())
        assertEquals(V2_SCHEMA_VERSION, payload.schemaVersion)
        assertEquals("100", payload.card("monthly_produced_ks")!!.value)
        assertEquals("8.5", payload.card("weekly_average_lessons")!!.value)
        assertEquals("12", payload.card("teacher_count")!!.value)
        assertNull(payload.card("monthly_lesson_count")!!.value)
        assertEquals("unavailable", payload.card("monthly_lesson_count")!!.availability)
        val cache = JSONObject(payload.toCacheJson())
        assertEquals(2, cache.getInt("schema_version"))
        assertEquals(16, cache.getJSONArray("cards").length())
    }

    @Test
    fun invalidImportCannotReplaceTheLastValidatedCache() {
        val oldCache = WidgetPayload.fromDashboardJson(v2Json()).toCacheJson()
        val invalid = JSONObject(v2Json()).apply { getJSONArray("cards").remove(15) }.toString()
        val retained = runCatching { WidgetPayload.fromDashboardJson(invalid).toCacheJson() }.getOrElse { oldCache }
        assertEquals(oldCache, retained)
        assertTrue(runCatching { WidgetPayload.fromDashboardJson("{bad json}") }.isFailure)
        assertTrue(runCatching { WidgetPayload.fromDashboardJson(v2Json().replace("\"schema_version\":2", "\"schema_version\":99")) }.isFailure)
    }
}
