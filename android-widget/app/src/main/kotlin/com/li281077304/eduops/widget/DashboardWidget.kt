package com.li281077304.eduops.widget

import android.content.Context
import java.net.HttpURLConnection
import java.net.URL

import androidx.compose.ui.unit.DpSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.glance.GlanceModifier
import androidx.glance.ImageProvider
import androidx.glance.appwidget.GlanceAppWidget
import androidx.glance.appwidget.GlanceAppWidgetReceiver
import androidx.glance.appwidget.SizeMode
import androidx.glance.appwidget.action.ActionCallback
import androidx.glance.appwidget.action.actionRunCallback
import androidx.glance.appwidget.provideContent
import androidx.glance.background
import androidx.glance.clickable
import androidx.glance.layout.Alignment
import androidx.glance.layout.Column
import androidx.glance.layout.Row
import androidx.glance.layout.Spacer
import androidx.glance.layout.defaultWeight
import androidx.glance.layout.fillMaxSize
import androidx.glance.layout.fillMaxWidth
import androidx.glance.layout.height
import androidx.glance.layout.padding
import androidx.glance.layout.width
import androidx.glance.text.FontWeight
import androidx.glance.text.Text
import androidx.glance.text.TextStyle
import androidx.glance.unit.ColorProvider

private class DashboardClient(private val context: Context) {
    fun fetch(): WidgetPayload {
        val endpoint = DashboardConfig.endpoint(context)
        val connection = (URL(endpoint).openConnection() as HttpURLConnection).apply {
            connectTimeout = 5_000
            readTimeout = 5_000
            requestMethod = "GET"
            setRequestProperty("Accept", "application/json")
        }
        return try {
            val response = connection
            if (response.responseCode !in 200..299) {
                error("Dashboard returned HTTP ${response.responseCode}")
            }
            val json = response.inputStream.bufferedReader().use { it.readText() }
            val payload = WidgetPayload.fromDashboardJson(json)
            DashboardConfig.savePayload(context, json)
            payload
        } finally {
            connection.disconnect()
        }
    }
}

class DashboardWidget : GlanceAppWidget() {
    override val sizeMode: SizeMode = SizeMode.Responsive(
        setOf(
            DpSize(180.dp, 220.dp),
            DpSize(280.dp, 300.dp),
        ),
    )

    override suspend fun provideGlance(context: Context, id: androidx.glance.GlanceId) {
        val state = runCatching { DashboardClient(context).fetch() }
            .fold(
                onSuccess = { WidgetState.Data(it) },
                onFailure = {
                    DashboardConfig.cachedPayload(context)?.let { WidgetState.Stale(it) }
                        ?: WidgetState.Error("暂时无法连接 Dashboard")
                },
            )
        provideContent { DashboardContent(state) }
    }
}

class DashboardWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget: GlanceAppWidget = DashboardWidget()
}

class RefreshWidgetAction : ActionCallback {
    override suspend fun onAction(
        context: Context,
        glanceId: androidx.glance.GlanceId,
        parameters: androidx.glance.action.ActionParameters,
    ) {
        DashboardWidget().update(context, glanceId)
    }
}

private sealed interface WidgetState {
    data class Data(val payload: WidgetPayload) : WidgetState
    data class Stale(val payload: WidgetPayload) : WidgetState
    data class Error(val message: String) : WidgetState
}

private fun cardModifier(weight: GlanceModifier): GlanceModifier = weight
    .padding(4.dp)
    .background(ImageProvider(R.drawable.widget_card_background))

@androidx.compose.runtime.Composable
private fun DashboardContent(state: WidgetState) {
    Column(
        modifier = GlanceModifier
            .fillMaxSize()
            .background(ImageProvider(R.drawable.widget_surface_background))
            .padding(12.dp),
        verticalAlignment = Alignment.Vertical.Top,
    ) {
        Text(
            text = "二校经营看板",
            modifier = GlanceModifier.clickable(actionRunCallback<RefreshWidgetAction>()),
            style = TextStyle(
                color = ColorProvider(R.color.widget_title),
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold,
            ),
        )
        when (state) {
            is WidgetState.Error -> ErrorContent(state.message)
            is WidgetState.Data -> DataContent(state.payload)
            is WidgetState.Stale -> DataContent(state.payload, stale = true)
        }
    }
}

@androidx.compose.runtime.Composable
private fun ErrorContent(message: String) {
    Spacer(GlanceModifier.height(8.dp))
    Text(text = message, style = TextStyle(color = ColorProvider(R.color.widget_muted), fontSize = 12.sp))
    Text(
        text = "请确认 Dashboard 服务可访问后刷新小组件",
        style = TextStyle(color = ColorProvider(R.color.widget_muted), fontSize = 10.sp),
    )
}

@androidx.compose.runtime.Composable
private fun DataContent(payload: WidgetPayload, stale: Boolean = false) {
    Spacer(GlanceModifier.height(2.dp))
    Text(
        text = "${payload.periodStart} ～ ${payload.periodEnd} · ${if (stale) "缓存 · " else "更新 "}${payload.updatedAt}",
        style = TextStyle(color = ColorProvider(R.color.widget_muted), fontSize = 10.sp),
    )
    Spacer(GlanceModifier.height(8.dp))
    payload.cards.chunked(2).forEach { row ->
        MetricRow(row.getOrNull(0), row.getOrNull(1))
    }
}

@androidx.compose.runtime.Composable
private fun MetricRow(left: WidgetCard?, right: WidgetCard?) {
    Row(modifier = GlanceModifier.fillMaxWidth()) {
        left?.let { MetricCardView(it, GlanceModifier.defaultWeight()) }
        if (left != null && right != null) Spacer(GlanceModifier.width(6.dp))
        right?.let { MetricCardView(it, GlanceModifier.defaultWeight()) }
    }
    Spacer(GlanceModifier.height(8.dp))
}

@androidx.compose.runtime.Composable
private fun MetricCardView(card: WidgetCard, weight: GlanceModifier) {
    Column(
        modifier = cardModifier(weight).padding(10.dp),
        verticalAlignment = Alignment.Vertical.CenterVertically,
    ) {
        Text(
            text = card.label,
            style = TextStyle(color = ColorProvider(R.color.widget_muted), fontSize = 11.sp),
        )
        Spacer(GlanceModifier.height(3.dp))
        Text(
            text = formatCard(card),
            style = TextStyle(
                color = ColorProvider(R.color.widget_value),
                fontSize = 15.sp,
                fontWeight = FontWeight.Bold,
            ),
        )
    }
}
