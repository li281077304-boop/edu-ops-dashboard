package com.li281077304.eduops.widget

import java.util.Locale

import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.DpSize
import androidx.compose.ui.unit.sp
import androidx.glance.GlanceModifier
import androidx.glance.ImageProvider
import androidx.glance.appwidget.GlanceAppWidget
import androidx.glance.appwidget.GlanceAppWidgetReceiver
import androidx.glance.appwidget.SizeMode
import androidx.glance.appwidget.provideContent
import androidx.glance.background
import androidx.glance.layout.Alignment
import androidx.glance.layout.Column
import androidx.glance.layout.Row
import androidx.glance.layout.Spacer
import androidx.glance.layout.fillMaxSize
import androidx.glance.layout.fillMaxWidth
import androidx.glance.layout.height
import androidx.glance.layout.padding
import androidx.glance.layout.width
import androidx.glance.text.FontWeight
import androidx.glance.text.Text
import androidx.glance.text.TextStyle
import androidx.glance.unit.ColorProvider

private data class MetricCard(val title: String, val value: String)

private fun formatKs(value: Double): String = String.format(Locale.US, "%.1f KS", value)

private val testCards = testDashboardMetrics.let { metrics ->
    listOf(
        MetricCard("月度已生产", "${metrics.monthlyProducedKs} KS"),
        MetricCard("月度预排", "${metrics.monthlyPlannedKs} KS"),
        MetricCard(
            "一对一周平均\nKS / 人 / 周",
            formatKs(weeklyAverageKs(metrics.oneToOneKs, metrics.oneToOneStudentCount, metrics.weeksInPeriod)),
        ),
        MetricCard(
            "全员周平均\nKS / 人 / 周",
            formatKs(weeklyAverageKs(metrics.totalKs, metrics.totalStudentCount, metrics.weeksInPeriod)),
        ),
        MetricCard("平均课次", "${metrics.averageLessons} 次"),
        MetricCard("大小周课时", "大周 1300 KS\n小周 700 KS"),
    )
}

class DashboardWidget : GlanceAppWidget() {
    override val sizeMode: SizeMode = SizeMode.Responsive(
        setOf(
            DpSize(180.dp, 220.dp),
            DpSize(280.dp, 300.dp),
        ),
    )

    override suspend fun provideGlance(context: android.content.Context, id: androidx.glance.GlanceId) {
        provideContent {
            DashboardContent()
        }
    }
}

class DashboardWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget: GlanceAppWidget = DashboardWidget()
}

private fun cardModifier(weight: GlanceModifier): GlanceModifier = weight
    .padding(4.dp)
    .background(ImageProvider(R.drawable.widget_card_background))

@androidx.compose.runtime.Composable
private fun DashboardContent() {
    Column(
        modifier = GlanceModifier
            .fillMaxSize()
            .background(ImageProvider(R.drawable.widget_surface_background))
            .padding(12.dp),
        verticalAlignment = Alignment.Vertical.Top,
    ) {
        Text(
            text = "二校经营看板",
            style = TextStyle(
                color = ColorProvider(R.color.widget_title),
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold,
            ),
        )
        Spacer(GlanceModifier.height(2.dp))
        Text(
            text = "数据更新时间：2026-09-15 15:30（测试数据）",
            style = TextStyle(
                color = ColorProvider(R.color.widget_muted),
                fontSize = 10.sp,
            ),
        )
        Spacer(GlanceModifier.height(10.dp))
        MetricRow(testCards[0], testCards[1])
        MetricRow(testCards[2], testCards[3])
        MetricRow(testCards[4], testCards[5])
    }
}

@androidx.compose.runtime.Composable
private fun MetricRow(left: MetricCard, right: MetricCard) {
    Row(modifier = GlanceModifier.fillMaxWidth()) {
        MetricCardView(left, GlanceModifier.defaultWeight())
        Spacer(GlanceModifier.width(6.dp))
        MetricCardView(right, GlanceModifier.defaultWeight())
    }
    Spacer(GlanceModifier.height(8.dp))
}

@androidx.compose.runtime.Composable
private fun MetricCardView(card: MetricCard, weight: GlanceModifier) {
    Column(
        modifier = cardModifier(weight)
            .padding(10.dp),
        verticalAlignment = Alignment.Vertical.CenterVertically,
    ) {
        Text(
            text = card.title,
            style = TextStyle(
                color = ColorProvider(R.color.widget_muted),
                fontSize = 11.sp,
            ),
        )
        Spacer(GlanceModifier.height(3.dp))
        Text(
            text = card.value,
            style = TextStyle(
                color = ColorProvider(R.color.widget_value),
                fontSize = 15.sp,
                fontWeight = FontWeight.Bold,
            ),
        )
    }
}
