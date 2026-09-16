package com.li281077304.eduops.widget

import android.content.Context
import android.content.Intent
import androidx.compose.runtime.Composable
import androidx.compose.ui.unit.DpSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.glance.GlanceModifier
import androidx.glance.ImageProvider
import androidx.glance.LocalContext
import androidx.glance.LocalSize
import androidx.glance.action.clickable
import androidx.glance.appwidget.GlanceAppWidget
import androidx.glance.appwidget.GlanceAppWidgetReceiver
import androidx.glance.appwidget.SizeMode
import androidx.glance.appwidget.action.actionStartActivity
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

class DashboardWidget : GlanceAppWidget() {
    override val sizeMode: SizeMode = SizeMode.Responsive(
        setOf(
            DpSize(180.dp, 220.dp),
            DpSize(280.dp, 300.dp),
        ),
    )

    override suspend fun provideGlance(context: Context, id: androidx.glance.GlanceId) {
        // Rendering is strictly local: network sync belongs to the app, never to a redraw.
        val payload = DashboardConfig.currentPayload(context)
        provideContent { DashboardContent(payload, DashboardConfig.isSample(context)) }
    }
}

class DashboardWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget: GlanceAppWidget = DashboardWidget()
}

@Composable
private fun DashboardContent(payload: WidgetPayload, isSample: Boolean) {
    val context = LocalContext.current
    val compact = LocalSize.current.width < 240.dp || LocalSize.current.height < 260.dp
    val cards = if (compact) payload.cards.take(4) else payload.cards
    Column(
        modifier = GlanceModifier
            .fillMaxSize()
            .background(ImageProvider(R.drawable.widget_surface_background))
            .padding(if (compact) 8.dp else 10.dp),
        verticalAlignment = Alignment.Vertical.Top,
    ) {
        Text(
            text = payload.dashboardName,
            modifier = GlanceModifier.clickable(actionStartActivity(Intent(context, MainActivity::class.java))),
            style = TextStyle(
                color = ColorProvider(R.color.widget_title),
                fontSize = if (compact) 15.sp else 17.sp,
                fontWeight = FontWeight.Bold,
            ),
        )
        Text(
            text = if (isSample) "示例数据 · 点击打开应用" else "更新 ${payload.updatedAt}",
            style = TextStyle(color = ColorProvider(R.color.widget_muted), fontSize = 9.sp),
        )
        if (!compact) {
            Text(
                text = payload.periodLabel,
                style = TextStyle(color = ColorProvider(R.color.widget_muted), fontSize = 9.sp),
            )
        }
        Spacer(GlanceModifier.height(if (compact) 5.dp else 7.dp))
        cards.chunked(2).forEach { row ->
            MetricRow(row, compact)
        }
    }
}

@Composable
private fun MetricRow(cards: List<WidgetCard>, compact: Boolean) {
    Row(modifier = GlanceModifier.fillMaxWidth()) {
        cards.getOrNull(0)?.let { MetricCardView(it, compact, GlanceModifier.defaultWeight()) }
        if (cards.size > 1) {
            Spacer(GlanceModifier.width(5.dp))
            MetricCardView(cards[1], compact, GlanceModifier.defaultWeight())
        }
    }
    Spacer(GlanceModifier.height(5.dp))
}

@Composable
private fun MetricCardView(card: WidgetCard, compact: Boolean, weight: GlanceModifier) {
    Column(
        modifier = weight
            .padding(3.dp)
            .background(ImageProvider(R.drawable.widget_card_background))
            .padding(if (compact) 7.dp else 8.dp),
        verticalAlignment = Alignment.Vertical.CenterVertically,
    ) {
        Text(
            text = card.label,
            style = TextStyle(color = ColorProvider(R.color.widget_muted), fontSize = 10.sp),
        )
        Spacer(GlanceModifier.height(2.dp))
        Text(
            text = formatCard(card),
            style = TextStyle(
                color = ColorProvider(R.color.widget_value),
                fontSize = if (card.key == "big_small_week_ks") 12.sp else 14.sp,
                fontWeight = FontWeight.Bold,
            ),
        )
    }
}
