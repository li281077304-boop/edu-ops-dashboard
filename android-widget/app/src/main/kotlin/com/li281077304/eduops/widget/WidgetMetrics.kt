package com.li281077304.eduops.widget

data class DashboardMetrics(
    val monthlyProducedKs: Int,
    val monthlyPlannedKs: Int,
    val oneToOneKs: Int,
    val oneToOneStudentCount: Int,
    val totalKs: Int,
    val totalStudentCount: Int,
    val weeksInPeriod: Int,
    val averageLessons: Double,
)

fun weeklyAverageKs(totalKs: Int, enrolledStudentCount: Int, weeksInPeriod: Int): Double {
    require(totalKs >= 0) { "totalKs must not be negative" }
    require(enrolledStudentCount > 0) { "enrolledStudentCount must be positive" }
    require(weeksInPeriod > 0) { "weeksInPeriod must be positive" }
    return totalKs.toDouble() / enrolledStudentCount / weeksInPeriod
}

internal val testDashboardMetrics = DashboardMetrics(
    monthlyProducedKs = 8420,
    monthlyPlannedKs = 10680,
    oneToOneKs = 1200,
    oneToOneStudentCount = 100,
    totalKs = 7680,
    totalStudentCount = 200,
    weeksInPeriod = 4,
    averageLessons = 12.4,
)
