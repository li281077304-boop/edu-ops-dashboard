package com.li281077304.eduops.widget

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.glance.appwidget.updateAll
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

private const val IMPORT_REQUEST = 1001

class MainActivity : Activity() {
    private lateinit var dashboardName: TextView
    private lateinit var status: TextView
    private lateinit var updated: TextView
    private lateinit var period: TextView
    private lateinit var message: TextView
    private lateinit var cards: LinearLayout
    private lateinit var endpoint: EditText
    private lateinit var advanced: View

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(buildContent())
        refreshSummary()
    }

    private fun buildContent(): View {
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(28, 36, 28, 28); setBackgroundColor(Color.WHITE) }
        fun text(size: Float, color: Int = Color.DKGRAY): TextView = TextView(this).apply { textSize = size; setTextColor(color); setPadding(0, 4, 0, 4) }
        root.addView(text(14f, Color.GRAY).apply { text = "经营看板 · 离线 Widget" })
        dashboardName = text(26f, Color.rgb(23, 35, 60)); root.addView(dashboardName)
        status = text(15f); root.addView(status)
        updated = text(13f, Color.GRAY); root.addView(updated)
        period = text(13f, Color.GRAY); root.addView(period)
        root.addView(Button(this).apply { text = "导入最新经营数据"; setOnClickListener { openImportPicker() } }, match())
        message = text(13f, Color.rgb(60, 90, 120)); root.addView(message)
        root.addView(text(18f, Color.rgb(23, 35, 60)).apply { text = "全部指标与口径" })
        cards = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }; root.addView(cards, match())
        root.addView(Button(this).apply { text = "高级设置"; setOnClickListener { advanced.visibility = if (advanced.visibility == View.VISIBLE) View.GONE else View.VISIBLE } }, match())
        advanced = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; visibility = View.GONE
            endpoint = EditText(this@MainActivity).apply { hint = "可选 HTTP endpoint"; setSingleLine(true); setText(DashboardConfig.endpoint(this@MainActivity)) }
            addView(endpoint, match())
            addView(Button(this@MainActivity).apply {
                text = "保存 endpoint"
                setOnClickListener { runCatching { DashboardConfig.setEndpoint(this@MainActivity, endpoint.text.toString()) }
                    .onSuccess { message.text = "endpoint 已保存；V0.2 不会自动联网" }
                    .onFailure { message.text = it.message ?: "地址无效" } }
            }, match())
            addView(text(12f, Color.GRAY).apply { text = "网络同步未启用；请通过文件导入更新 Widget。" })
        }
        root.addView(advanced)
        root.addView(text(12f, Color.GRAY).apply { text = "导入成功后会校验并持久保存；无网络时持续显示最近一次成功数据。"; setPadding(0, 20, 0, 0) })
        return ScrollView(this).apply { addView(root) }
    }

    private fun refreshSummary() {
        val payload = runCatching { DashboardConfig.currentPayload(this) }.getOrElse { message.text = "本地数据不可用：${it.message}"; return }
        dashboardName.text = payload.dashboardName
        status.text = if (DashboardConfig.cachedPayload(this) == null) "● 尚未导入数据" else "● 已保存数据（离线可用）"
        updated.text = "最近更新：${payload.updatedAt}"
        period.text = "数据周期：${payload.periodLabel}"
        cards.removeAllViews()
        payload.cards.forEach { card -> cards.addView(TextView(this).apply {
            setTextColor(Color.DKGRAY); setPadding(0, 12, 0, 12)
            text = "${card.section} · ${card.label}\n${formatCard(card)}\n口径：${card.definition}"
        }, match()) }
    }

    private fun openImportPicker() {
        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE); type = "application/json"
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        }, IMPORT_REQUEST)
    }

    @Deprecated("Activity result API kept for the minimal Android-only distribution")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != IMPORT_REQUEST || resultCode != RESULT_OK) return
        val uri: Uri = data?.data ?: return
        runCatching {
            val granted = data.flags and Intent.FLAG_GRANT_READ_URI_PERMISSION
            if (granted != 0) contentResolver.takePersistableUriPermission(uri, granted)
            val json = contentResolver.openInputStream(uri)?.bufferedReader()?.use { it.readText() } ?: error("无法读取文件")
            DashboardConfig.saveImportedPayload(this, json)
        }.onSuccess {
            CoroutineScope(Dispatchers.Main).launch {
                DashboardWidget().updateAll(this@MainActivity)
                message.text = "导入成功，已刷新 Widget"
                refreshSummary()
            }
        }.onFailure { message.text = "导入失败，原有缓存未改变：${it.message ?: "文件格式无效"}" }
    }

    private fun match(): ViewGroup.LayoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
}
