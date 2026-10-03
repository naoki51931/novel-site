package com.novelsite.mobile

import android.app.Activity
import android.content.Context
import android.util.AttributeSet
import androidx.activity.ComponentActivity
import androidx.appcompat.widget.AppCompatButton

class BackButton @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = android.R.attr.buttonStyle
) : AppCompatButton(context, attrs, defStyleAttr) {
    init {
        setOnClickListener {
            val activity = context as? Activity ?: return@setOnClickListener
            if (activity is ComponentActivity) {
                activity.onBackPressedDispatcher.onBackPressed()
            } else {
                activity.finish()
            }
        }
    }
}
