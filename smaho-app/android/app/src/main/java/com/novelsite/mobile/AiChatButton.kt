package com.novelsite.mobile
import android.content.Context
import android.content.Intent
import android.util.AttributeSet
import androidx.appcompat.widget.AppCompatButton
class AiChatButton @JvmOverloads constructor(context:Context,attrs:AttributeSet?=null,defStyleAttr:Int=android.R.attr.buttonStyle):AppCompatButton(context,attrs,defStyleAttr){init{setOnClickListener{context.startActivity(Intent(context,AiChatActivity::class.java))}}}