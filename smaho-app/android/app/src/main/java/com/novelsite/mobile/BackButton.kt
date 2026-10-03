package com.novelsite.mobile

import android.app.Activity
import android.content.Context
import android.util.AttributeSet
import androidx.appcompat.widget.AppCompatButton

class BackButton @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = android.R.attr.buttonStyle
) : AppCompatButton(context, attrs, defStyleAttr) {
    init {
        setOnClickListener {
            (context as? Activity)?.onBackPressedDispatcher?.onBackPressed()
                ?: (context as? Activity)?.finish()
        }
    }
}
