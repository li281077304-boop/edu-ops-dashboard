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
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

private const val IMPORT_REQUEST = 1001

internal class DashboardClient(private val context: Activity) {
    fun fetchJson(): String {
        val connection = (URL(DashboardConfig.endpoint(context)).openConnection() as HttpURLConnection).apply {
            connectTimeout = 5_000
            readTimeout = 5_000
            requestMethod = "GET"
            setRequestProperty("Accept", "application/json")
        }
        return try {
            require(connection.responseCode in 200..299) { "Dashboard 返回 HTTP ${connection.responseCode}" }
            val json = connection.inputStream.bufferedReader().use { it.readText() }
            WidgetPayload.fromDashboardJson(json)
            json
        } finally {
            connection.disconnect()
        }
    }
}

class MainActivity : Activity() {
    private lateinit var dashboardName: TextView
    private lateinit var status: TextView
    private lateinit var updated: TextView
    private lateinit var period: TextView
    private lateinit var message: TextView
    private lateinit var endpoint: EditText
    private lateinit var dashboardId: EditText
    private lateinit var advanced: View

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(buildContent())
        refreshSummary()
    }

    private fun buildContent(): View {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(28, 36, 28, 28)
            setBackgroundColor(Color.WHITE)
        }
        fun text(size: Float, color: Int = Color.DKGRAY): TextView = TextView(this).apply {
            textSize = size
            setTextColor(color)
            setPadding(0, 4, 0, 4)
        }
        root.addView(text(14f, Color.GRAY).apply { text = "经营看板" })
        dashboardName = text(26f, Color.rgb(23, 35, 60))
        root.addView(dashboardName)
        status = text(15f)
        root.addView(status)
        updated = text(13f, Color.GRAY)
        root.addView(updated)
        period = text(13f, Color.GRAY)
        root.addView(period)

        val sync = Button(this).apply {
            text = "同步最新数据"
            setOnClickListener { syncLatest(this) }
        }
        root.addView(sync, match())
        val import = Button(this).apply {
            text = "导入数据文件"
            setOnClickListener { openImportPicker() }
        }
        root.addView(import, match())
        message = text(13f, Color.rgb(60, 90, 120))
        root.addView(message)

        val advancedToggle = Button(this).apply {
            text = "高级设置"
            setOnClickListener { advanced.visibility = if (advanced.visibility == View.VISIBLE) View.GONE else View.VISIBLE }
        }
        root.addView(advancedToggle, match())
        advanced = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            visibility = View.GONE
            endpoint = EditText(this@MainActivity).apply {
                hint = "Dashboard 数据地址（http(s) URL）"
                setSingleLine(true)
                setText(DashboardConfig.endpoint(this@MainActivity))
            }
            dashboardId = EditText(this@MainActivity).apply {
                hint = "Dashboard ID"
                setSingleLine(true)
                setText(DashboardConfig.dashboardId(this@MainActivity))
            }
            addView(endpoint, match())
            addView(dashboardId, match())
            addView(Button(this@MainActivity).apply {
                text = "保存设置"
                setOnClickListener {
                    runCatching { DashboardConfig.setSettings(this@MainActivity, endpoint.text.toString(), dashboardId.text.toString()) }
                        .onSuccess { message.text = "设置已保存" }
                        .onFailure { message.text = it.message ?: "设置无效" }
                }
            }, match())
        }
        root.addView(advanced)
        root.addView(text(12f, Color.GRAY).apply {
            text = "数据来源可为 API 或 widget-data.json。Widget 只使用本地最近成功数据，断网仍可查看。"
            setPadding(0, 20, 0, 0)
        })
        return ScrollView(this).apply { addView(root) }
    }

    private fun refreshSummary() {
        val payload = runCatching { DashboardConfig.cachedPayload(this) ?: DashboardConfig.samplePayload(this) }.getOrElse {
            message.text = "内置示例数据不可用：${it.message}"
            return
        }
        dashboardName.text = payload.dashboardName
        status.text = if (DashboardConfig.isSample(this)) "● 示例数据" else "● 已保存数据（离线可用）"
        updated.text = "最近更新：${payload.updatedAt}"
        period.text = "数据周期：${payload.periodLabel}"
    }

    private fun syncLatest(button: Button) {
        button.isEnabled = false
        message.text = "正在同步…"
        CoroutineScope(Dispatchers.IO).launch {
            runCatching {
                val json = DashboardClient(this@MainActivity).fetchJson()
                DashboardConfig.savePayload(this@MainActivity, json)
                DashboardWidget().updateAll(this@MainActivity)
            }.onSuccess {
                withContext(Dispatchers.Main) {
                    message.text = "同步成功，已刷新 Widget"
                    refreshSummary()
                    button.isEnabled = true
                }
            }.onFailure {
                withContext(Dispatchers.Main) {
                    message.text = "同步失败，保留原有数据：${it.message ?: "网络不可用"}"
                    refreshSummary()
                    button.isEnabled = true
                }
            }
        }
    }

    private fun openImportPicker() {
        startActivityForResult(
            Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = "application/json"
            },
            IMPORT_REQUEST,
        )
    }

    @Deprecated("Activity result API kept minimal for the P0.1 distribution build")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != IMPORT_REQUEST || resultCode != RESULT_OK) return
        val uri: Uri = data?.data ?: return
        runCatching {
            val json = contentResolver.openInputStream(uri)?.bufferedReader()?.use { it.readText() }
                ?: error("无法读取文件")
            DashboardConfig.savePayload(this, json)
        }.onSuccess {
            CoroutineScope(Dispatchers.Main).launch {
                DashboardWidget().updateAll(this@MainActivity)
                message.text = "导入成功，已刷新 Widget"
                refreshSummary()
            }
        }.onFailure {
            message.text = "导入失败，原有数据未改变：${it.message ?: "文件格式无效"}"
        }
    }

    private fun match(): ViewGroup.LayoutParams =
        ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
}
