package com.li281077304.eduops.widget

import android.app.Activity
import android.os.Bundle
import android.widget.TextView

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(
            TextView(this).apply {
                text = "二校经营看板\n\n长按主屏 → 小组件 → 添加经营看板"
                textSize = 18f
                setPadding(32, 48, 32, 32)
            },
        )
    }
}
