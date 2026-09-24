package com.li281077304.eduops.widget

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.widget.Button
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

        val import = Button(this).apply {
            text = "导入最新经营数据"
            setOnClickListener { openImportPicker() }
        }
        root.addView(import, match())
        message = text(13f, Color.rgb(60, 90, 120))
        root.addView(message)

        root.addView(text(12f, Color.GRAY).apply {
            text = "导入 widget-data.json 后，Widget 使用本地最近成功数据；断网仍可查看。"
            setPadding(0, 20, 0, 0)
        })
        return ScrollView(this).apply { addView(root) }
    }

    private fun refreshSummary() {
        val payload = DashboardConfig.currentPayload(this)
        if (payload == null) {
            dashboardName.text = "经营看板"
            status.text = "尚未导入数据"
            updated.text = ""
            period.text = "选择最新的 widget-data.json 开始使用"
            return
        }
        dashboardName.text = payload.dashboardName
        status.text = "● 已导入数据（离线可用）"
        updated.text = "最近更新：${payload.updatedAt}"
        period.text = "数据周期：${payload.periodLabel}"
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
