package com.novelsite.mobile

import android.content.Context
import android.util.AttributeSet
import android.view.View
import android.widget.AdapterView
import android.widget.SpinnerAdapter
import androidx.appcompat.widget.AppCompatSpinner

class PersistedModelSpinner @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = androidx.appcompat.R.attr.spinnerStyle
) : AppCompatSpinner(context, attrs, defStyleAttr) {

    private val prefs = context.getSharedPreferences("lexis_native_ai_chat", Context.MODE_PRIVATE)
    private var restoring = false

    override fun setAdapter(adapter: SpinnerAdapter?) {
        super.setAdapter(adapter)
        val savedModel = prefs.getString("selected_model", "").orEmpty()
        if (adapter != null && savedModel.isNotBlank()) {
            for (i in 0 until adapter.count) {
                if (adapter.getItem(i)?.toString() == savedModel) {
                    restoring = true
                    setSelection(i, false)
                    restoring = false
                    break
                }
            }
        }
        onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                if (!restoring) {
                    adapter?.getItem(position)?.toString()?.takeIf { it.isNotBlank() }?.let {
                        prefs.edit().putString("selected_model", it).apply()
                    }
                }
            }
            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
        }
    }
}
