package com.li281077304.eduops.widget

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.glance.appwidget.updateAll
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val endpoint = EditText(this).apply {
            setText(DashboardConfig.endpoint(this@MainActivity))
            hint = "http://192.168.1.20:8787/api/status"
            setSingleLine(true)
        }
        val message = TextView(this).apply { setTextColor(Color.DKGRAY) }
        val refresh = Button(this).apply {
            text = "保存并刷新小组件"
            setOnClickListener {
                runCatching { DashboardConfig.setEndpoint(this@MainActivity, endpoint.text.toString()) }
                    .onSuccess {
                        message.text = "已保存。正在刷新小组件…"
                        CoroutineScope(Dispatchers.IO).launch { DashboardWidget().updateAll(this@MainActivity) }
                    }
                    .onFailure { message.text = it.message ?: "地址无效" }
            }
        }
        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 48, 32, 32)
            addView(TextView(context).apply {
                text = "二校经营看板\n\n模拟器默认使用 10.0.2.2；实体设备请输入电脑在同一局域网内的地址。点击小组件标题也可刷新。"
                textSize = 18f
            }, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            addView(endpoint, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            addView(refresh, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            addView(message, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        })
    }
}
