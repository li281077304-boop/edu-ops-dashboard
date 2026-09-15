package com.li281077304.eduops.widget

import org.junit.Assert.assertEquals
import org.junit.Test

class WidgetMetricsTest {
    @Test
    fun fourWeeksFourLessonsAtThreeKsPerLessonIsThreeKsPerStudentPerWeek() {
        assertEquals(3.0, weeklyAverageKs(totalKs = 12, enrolledStudentCount = 1, weeksInPeriod = 4), 0.0001)
    }

    @Test
    fun fourWeeksTwoLessonsAtThreeKsPerLessonIsOnePointFiveKsPerStudentPerWeek() {
        assertEquals(1.5, weeklyAverageKs(totalKs = 6, enrolledStudentCount = 1, weeksInPeriod = 4), 0.0001)
    }

    @Test
    fun oneToOneAndAllStudentAveragesUseTheirOwnDenominators() {
        val metrics = testDashboardMetrics
        assertEquals(
            3.0,
            weeklyAverageKs(metrics.oneToOneKs, metrics.oneToOneStudentCount, metrics.weeksInPeriod),
            0.0001,
        )
        assertEquals(
            9.6,
            weeklyAverageKs(metrics.totalKs, metrics.totalStudentCount, metrics.weeksInPeriod),
            0.0001,
        )
    }
}
