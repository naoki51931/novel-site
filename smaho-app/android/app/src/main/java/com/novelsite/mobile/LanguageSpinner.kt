package com.novelsite.mobile

import android.content.Context
import android.util.AttributeSet
import android.view.View
import android.view.ViewGroup
import android.widget.*

class LanguageSpinner @JvmOverloads constructor(c:Context,a:AttributeSet?=null):Spinner(c,a){
 private val codes=listOf("ja","en","ko","zh-CN","zh-TW","vi")
 private val names=listOf("日本語","English","한국어","简体中文","繁體中文","Tiếng Việt")
 private val base=java.util.WeakHashMap<TextView,String>()
 override fun onAttachedToWindow(){super.onAttachedToWindow();adapter=ArrayAdapter(context,android.R.layout.simple_spinner_dropdown_item,names);val saved=context.getSharedPreferences("lexis_ui",Context.MODE_PRIVATE).getString("language","ja")?:"ja";setSelection(codes.indexOf(saved).coerceAtLeast(0));onItemSelectedListener=object:AdapterView.OnItemSelectedListener{override fun onNothingSelected(p:AdapterView<*>?){};override fun onItemSelected(p:AdapterView<*>?,v:View?,pos:Int,id:Long){val code=codes[pos];context.getSharedPreferences("lexis_ui",Context.MODE_PRIVATE).edit().putString("language",code).apply();post{translate(rootView,code)}}};post{translate(rootView,saved)}}
 private fun translate(v:View,lang:String){if(v===this)return;if(v is TextView){if(!base.containsKey(v))base[v]=v.text.toString();val jp=base[v].orEmpty();v.text=if(lang=="ja")jp else words[lang]?.get(jp)?:jp;if(v is EditText){val h=v.hint?.toString().orEmpty();val key="hint:$h";v.hint=words[lang]?.get(key)?:h}};if(v is ViewGroup)for(i in 0 until v.childCount)translate(v.getChildAt(i),lang)}
 companion object{val words=mapOf(
 "en" to mapOf("生成" to "Generate","小説一覧" to "Novels","生成した小説一覧" to "Generated novels","OpenRouterで小説を生成" to "Generate novels with OpenRouter","OpenRouterでAPIキーを取得・管理" to "Get / manage OpenRouter API key","APIキーを安全に保存" to "Save API key securely","AIモデル" to "AI model","モデル一覧を取得" to "Load models","ブロック生成" to "Block generation","+ ブロックを追加" to "+ Add block","再試行回数" to "Retries","テンプレート保存" to "Save template","選択したテンプレートを読み込む" to "Load selected template","通常生成" to "Generate","続きを生成" to "Continue","端末に下書き保存" to "Save draft","TXTとして共有" to "Share as TXT","Lexisへ投稿" to "Post to Lexis","Lexisへアップロード" to "Upload to Lexis","hint:タイトル" to "Title","hint:ジャンル" to "Genre","hint:登場人物" to "Characters","hint:雰囲気・文体" to "Tone / style","hint:あらすじ・生成指示" to "Synopsis / instructions","hint:テンプレート名" to "Template name","hint:生成結果" to "Generated text"),
 "ko" to mapOf("生成" to "생성","小説一覧" to "소설 목록","生成した小説一覧" to "생성한 소설","OpenRouterで小説を生成" to "OpenRouter로 소설 생성","モデル一覧を取得" to "모델 목록 가져오기","ブロック生成" to "블록 생성","+ ブロックを追加" to "+ 블록 추가","再試行回数" to "재시도 횟수","テンプレート保存" to "템플릿 저장","通常生成" to "일반 생성","続きを生成" to "계속 생성","Lexisへ投稿" to "Lexis에 게시","Lexisへアップロード" to "Lexis에 업로드","hint:タイトル" to "제목","hint:ジャンル" to "장르","hint:登場人物" to "등장인물","hint:雰囲気・文体" to "분위기·문체"),
 "zh-CN" to mapOf("生成" to "生成","小説一覧" to "小说列表","生成した小説一覧" to "已生成小说","モデル一覧を取得" to "获取模型列表","ブロック生成" to "分块生成","+ ブロックを追加" to "+ 添加块","再試行回数" to "重试次数","テンプレート保存" to "保存模板","通常生成" to "普通生成","続きを生成" to "继续生成","Lexisへ投稿" to "发布到Lexis","hint:タイトル" to "标题","hint:ジャンル" to "类型","hint:登場人物" to "人物"),
 "zh-TW" to mapOf("生成" to "生成","小説一覧" to "小說列表","生成した小説一覧" to "已生成小說","モデル一覧を取得" to "取得模型列表","ブロック生成" to "分塊生成","+ ブロックを追加" to "+ 新增區塊","再試行回数" to "重試次數","テンプレート保存" to "儲存範本","通常生成" to "一般生成","続きを生成" to "繼續生成","Lexisへ投稿" to "發布到Lexis","hint:タイトル" to "標題","hint:ジャンル" to "類型","hint:登場人物" to "人物"),
 "vi" to mapOf("生成" to "Tạo","小説一覧" to "Danh sách tiểu thuyết","生成した小説一覧" to "Tiểu thuyết đã tạo","モデル一覧を取得" to "Tải danh sách mô hình","ブロック生成" to "Tạo theo khối","+ ブロックを追加" to "+ Thêm khối","再試行回数" to "Số lần thử lại","テンプレート保存" to "Lưu mẫu","通常生成" to "Tạo thường","続きを生成" to "Viết tiếp","Lexisへ投稿" to "Đăng lên Lexis","hint:タイトル" to "Tiêu đề","hint:ジャンル" to "Thể loại","hint:登場人物" to "Nhân vật")
 )}
}
