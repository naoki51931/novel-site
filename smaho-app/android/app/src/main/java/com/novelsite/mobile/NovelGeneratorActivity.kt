package com.novelsite.mobile
import android.content.Intent
import android.os.Bundle
import android.os.Environment
import android.content.ContentValues
import android.provider.MediaStore
import android.view.View
import android.view.MotionEvent
import android.text.method.ScrollingMovementMethod
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class NovelGeneratorActivity:AppCompatActivity(){
 private val defaultNovelTitle="Lexis生成小説"
 private fun novelTitle(v:String):String{val t=v.trim();return if(t.isBlank()||t=="無題"||t=="タイトル未設定")defaultNovelTitle else t}
 private val client=OkHttpClient.Builder().connectTimeout(30,TimeUnit.SECONDS).readTimeout(180,TimeUnit.SECONDS).build()
 private lateinit var key:EditText; private lateinit var model:Spinner; private lateinit var title:EditText; private lateinit var genre:EditText
 private lateinit var chars:EditText; private lateinit var mood:EditText; private lateinit var prompt:EditText; private lateinit var adult:CheckBox
 private lateinit var blocks:EditText; private lateinit var tokens:EditText; private lateinit var result:EditText; private lateinit var progress:ProgressBar; private lateinit var status:TextView
 private lateinit var email:EditText; private lateinit var password:EditText; private lateinit var blockPromptContainer:LinearLayout; private lateinit var retryCount:EditText
 private lateinit var generationPanel:LinearLayout; private lateinit var libraryPanel:LinearLayout; private lateinit var libraryContainer:LinearLayout
 private var downloadNovel:JSONObject?=null
 private val prefs by lazy{val mk=MasterKey.Builder(this).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build();EncryptedSharedPreferences.create(this,"lexis_secure",mk,EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM)}
 override fun onCreate(b:Bundle?){super.onCreate(b);setContentView(R.layout.activity_novel_generator)
  key=findViewById(R.id.apiKey);model=findViewById(R.id.modelSpinner);title=findViewById(R.id.titleInput);genre=findViewById(R.id.genreInput);chars=findViewById(R.id.charactersInput);mood=findViewById(R.id.moodInput);prompt=findViewById(R.id.instructionInput);adult=findViewById(R.id.r18Check);blocks=findViewById(R.id.blockCount);tokens=findViewById(R.id.maxTokens);result=findViewById(R.id.resultText);progress=findViewById(R.id.progress);status=findViewById(R.id.status);email=findViewById(R.id.lexisEmail);password=findViewById(R.id.lexisPassword);blockPromptContainer=findViewById(R.id.blockPromptContainer);retryCount=findViewById(R.id.retryCount);generationPanel=findViewById(R.id.generationPanel);libraryPanel=findViewById(R.id.libraryPanel);libraryContainer=findViewById(R.id.libraryContainer)
  key.setText(prefs.getString("openrouter_key","")); setModels(listOf("openrouter/auto")); addBlockPrompt(); addBlockPrompt(); addBlockPrompt()
  enableTextEditing(key);enableTextEditing(title);enableTextEditing(genre);enableTextEditing(chars);enableTextEditing(mood);enableTextEditing(prompt);enableTextEditing(blocks);enableTextEditing(tokens);enableTextEditing(retryCount);enableTextEditing(email);enableTextEditing(password);enableTextEditing(result)
  result.movementMethod=ScrollingMovementMethod.getInstance()
  result.setOnTouchListener{v,e->
   if(e.action==MotionEvent.ACTION_DOWN||e.action==MotionEvent.ACTION_MOVE)v.parent?.requestDisallowInterceptTouchEvent(true)
   if(e.action==MotionEvent.ACTION_UP||e.action==MotionEvent.ACTION_CANCEL)v.parent?.requestDisallowInterceptTouchEvent(false)
   false
  }
  findViewById<Button>(R.id.navGenerate).setOnClickListener{showGenerator()};findViewById<Button>(R.id.navLibrary).setOnClickListener{showLibrary()}
  findViewById<Button>(R.id.addBlockPrompt).setOnClickListener{addBlockPrompt()}
  findViewById<Button>(R.id.saveApiKey).setOnClickListener{prefs.edit().putString("openrouter_key",key.text.toString().trim()).apply();toast("APIキーを保存しました")}
  findViewById<Button>(R.id.loadModels).setOnClickListener{loadModels()};findViewById<Button>(R.id.generate).setOnClickListener{generate(false)};findViewById<Button>(R.id.generateBlocks).setOnClickListener{generate(true)}
  findViewById<Button>(R.id.continueButton).setOnClickListener{continueStory()};findViewById<Button>(R.id.saveDraft).setOnClickListener{saveDraft()};findViewById<Button>(R.id.shareText).setOnClickListener{share()};findViewById<Button>(R.id.uploadLexis).setOnClickListener{loginUpload()}
 }
 private fun enableTextEditing(v:EditText){v.isLongClickable=true;v.setTextIsSelectable(true);v.customSelectionActionModeCallback=null;v.customInsertionActionModeCallback=null}
 private fun addBlockPrompt(){
  val e=EditText(this);enableTextEditing(e);e.hint="ブロック "+(blockPromptContainer.childCount+1)+" の指示";e.minLines=3;e.gravity=android.view.Gravity.TOP;e.inputType=android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE or android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES;e.setPadding(24,18,24,18)
  val lp=LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT,LinearLayout.LayoutParams.WRAP_CONTENT);lp.setMargins(0,8,0,8);e.layoutParams=lp;blockPromptContainer.addView(e);blocks.setText(blockPromptContainer.childCount.toString())
  e.setOnEditorActionListener{_,_,_->if(e===blockPromptContainer.getChildAt(blockPromptContainer.childCount-1)){addBlockPrompt();true}else false}
 }
 private fun blockPrompts(): List<String> = (0 until blockPromptContainer.childCount).map { index -> (blockPromptContainer.getChildAt(index) as EditText).text.toString().trim() }
 private fun k()=key.text.toString().trim();private fun m()=model.selectedItem?.toString()?:"openrouter/auto";private fun limit()=(tokens.text.toString().toIntOrNull()?:2000).coerceIn(512,8192)
 private fun retries()=(retryCount.text.toString().toIntOrNull()?:20).coerceIn(0,100)
 private fun base():String{val a=if(adult.isChecked)"\n成人向け表現を許可。ただし登場人物は全員18歳以上で、合意のある成人同士の関係のみ。" else "";return "日本語の小説を書いてください。\nタイトル: "+title.text+"\nジャンル: "+genre.text+"\n登場人物: "+chars.text+"\n雰囲気・文体: "+mood.text+"\n指示・あらすじ: "+prompt.text+a+"\n説明ではなく小説本文を出力してください。"}
 private fun setModels(x:List<String>){model.adapter=ArrayAdapter(this,android.R.layout.simple_spinner_dropdown_item,x)}
 private fun loadModels(){if(k().isBlank())return toast("APIキーを入力してください");busy(true,"モデル取得中…");val q=Request.Builder().url("https://openrouter.ai/api/v1/models").header("Authorization","Bearer "+k()).build();client.newCall(q).enqueue(object:Callback{override fun onFailure(c:Call,e:IOException)=err(e.message?:"通信エラー");override fun onResponse(c:Call,r:Response){r.use{if(!it.isSuccessful)return err("モデル取得失敗 HTTP "+it.code);val a=JSONObject(it.body?.string().orEmpty()).optJSONArray("data")?:JSONArray();val x=(0 until a.length()).mapNotNull{i->a.optJSONObject(i)?.optString("id")?.takeIf{v->v.isNotBlank()}}.sorted();runOnUiThread{setModels(x.ifEmpty{listOf("openrouter/auto")});busy(false,x.size.toString()+"モデル取得")}}}})}
 private fun generate(multi:Boolean){if(k().isBlank())return toast("APIキーを入力してください");if(prompt.text.isBlank())return toast("生成指示を入力してください");if(!multi){call(base()){result.setText(it);saveNovelToLibrary(novelTitle(title.text.toString()),it,adult.isChecked);busy(false,"生成完了")};return};val filled=blockPrompts();val n=maxOf((blocks.text.toString().toIntOrNull()?:filled.size).coerceIn(2,12),filled.size.coerceAtMost(12));result.setText("");block(1,n,"",filled)}
 private fun block(i:Int,n:Int,old:String,instructions:List<String>){busy(true,i.toString()+" / "+n+" ブロック生成中…");val context=if(old.isBlank())"" else "\n\nここまでの本文:\n"+old.takeLast(12000);val specific=instructions.getOrNull(i-1).orEmpty();val direction=if(specific.isBlank())"" else "\nこのブロック固有の指示: "+specific;call(base()+"\n\n全"+n+"ブロック中の第"+i+"ブロックを書いてください。前後を自然につないでください。"+direction+context){p->val all=if(old.isBlank())p else old+"\n\n"+p;result.setText(all);if(i<n)block(i+1,n,all,instructions)else{saveNovelToLibrary(novelTitle(title.text.toString()),all,adult.isChecked);busy(false,"ブロック生成完了")}}}
 private fun continueStory(){val old=result.text.toString();if(old.isBlank())return toast("本文がありません");call(base()+"\n\n以下の本文の直後から続きを書いてください。\n\n"+old.takeLast(14000)){p->result.setText(old+"\n\n"+p);saveNovelToLibrary(novelTitle(title.text.toString()),result.text.toString(),adult.isChecked);busy(false,"続きを生成しました")}}
 private fun call(p:String,done:(String)->Unit){busy(true,"生成中…");callAttempt(p,done,0,retries())}
 private fun callAttempt(p:String,done:(String)->Unit,attempt:Int,maxRetries:Int){
  val body=JSONObject().put("model",m()).put("max_tokens",limit()).put("messages",JSONArray().put(JSONObject().put("role","user").put("content",p)))
  val q=Request.Builder().url("https://openrouter.ai/api/v1/chat/completions").header("Authorization","Bearer "+k()).header("Content-Type","application/json").header("HTTP-Referer","https://shosetsu-toukou-site.org").header("X-Title","Lexis Android").post(body.toString().toRequestBody("application/json".toMediaType())).build()
  client.newCall(q).enqueue(object:Callback{
   override fun onFailure(c:Call,e:IOException){retryOrFail(p,done,attempt,maxRetries,e.message?:"通信エラー")}
   override fun onResponse(c:Call,r:Response){r.use{
    val raw=it.body?.string().orEmpty()
    if(it.code==401||it.code==403)return err("OpenRouter APIキーが無効です。APIキーを確認してください。")
    if(!it.isSuccessful)return retryOrFail(p,done,attempt,maxRetries,"生成失敗 HTTP "+it.code+"\n"+raw.take(400))
    val text=runCatching{JSONObject(raw).getJSONArray("choices").getJSONObject(0).getJSONObject("message").getString("content")}.getOrNull()?.trim().orEmpty()
    if(text.isBlank()||text.equals("null",ignoreCase=true))return retryOrFail(p,done,attempt,maxRetries,"AIから空またはnullの応答が返りました。")
    runOnUiThread{done(text)}
   }}
  })
 }
 private fun retryOrFail(p:String,done:(String)->Unit,attempt:Int,maxRetries:Int,message:String){
  if(attempt>=maxRetries)return err(message+"（再試行上限 "+maxRetries+" 回）")
  runOnUiThread{status.text="再試行 "+(attempt+1)+" / "+maxRetries+"…"}
  android.os.Handler(mainLooper).postDelayed({callAttempt(p,done,attempt+1,maxRetries)},minOf(5000L,500L+attempt*250L))
 }
 private fun showGenerator(){generationPanel.visibility=View.VISIBLE;libraryPanel.visibility=View.GONE}
 private fun showLibrary(){generationPanel.visibility=View.GONE;libraryPanel.visibility=View.VISIBLE;migrateLibraryToPersistentFiles();renderLibrary()}
 private fun libraryPrefs()=getSharedPreferences("lexis_novel_library",MODE_PRIVATE)
 private fun loadLibrary():JSONArray=runCatching{JSONArray(libraryPrefs().getString("novels","[]"))}.getOrDefault(JSONArray())
 private fun persistNovelFile(id:Long,t:String,b:String){
  if(android.os.Build.VERSION.SDK_INT>=29){
   val values=ContentValues().apply{put(MediaStore.MediaColumns.DISPLAY_NAME,novelTitle(t).replace(Regex("[\\/:*?\"<>|]"),"_")+"_"+id+".txt");put(MediaStore.MediaColumns.MIME_TYPE,"text/plain");put(MediaStore.MediaColumns.RELATIVE_PATH,Environment.DIRECTORY_DOCUMENTS+"/Lexis/小説")}
   runCatching{contentResolver.insert(MediaStore.Files.getContentUri("external"),values)?.let{uri->contentResolver.openOutputStream(uri,"w")?.bufferedWriter(Charsets.UTF_8)?.use{w->w.write(novelTitle(t));w.write("\n\n");w.write(b)}}}
  }
 }
 private fun migrateLibraryToPersistentFiles(){val a=loadLibrary();for(i in 0 until a.length()){val n=a.optJSONObject(i)?:continue;if(!n.optBoolean("persistentSaved",false)){persistNovelFile(n.optLong("id"),n.optString("title",""),n.optString("body",""));n.put("persistentSaved",true)}};libraryPrefs().edit().putString("novels",a.toString()).apply()}
 private fun saveNovelToLibrary(t:String,b:String,r18:Boolean){
  if(b.isBlank())return
  val old=loadLibrary();val out=JSONArray();val id=System.currentTimeMillis();persistNovelFile(id,t,b);out.put(JSONObject().put("id",id).put("savedAt",id).put("title",novelTitle(t)).put("body",b).put("r18",r18).put("persistentSaved",true))
  for(i in 0 until minOf(old.length(),199))out.put(old.getJSONObject(i))
  libraryPrefs().edit().putString("novels",out.toString()).apply()
 }
 private fun replaceUntitledLibraryNovels(){
  val old=loadLibrary();val out=JSONArray();var changed=0
  for(i in 0 until old.length()){val n=old.getJSONObject(i);val current=n.optString("title","").trim();if(current.isBlank()||current=="無題"||current=="タイトル未設定"){n.put("title",defaultNovelTitle);changed++};out.put(n)}
  libraryPrefs().edit().putString("novels",out.toString()).apply();toast(changed.toString()+"件のタイトルを「"+defaultNovelTitle+"」に置き換えました");renderLibrary()
 }
 private fun deleteLibraryNovel(id:Long){val old=loadLibrary();val out=JSONArray();for(i in 0 until old.length()){val n=old.getJSONObject(i);if(n.optLong("id")!=id)out.put(n)};libraryPrefs().edit().putString("novels",out.toString()).apply();renderLibrary()}
 private fun renderLibrary(){
  libraryContainer.removeAllViews();val a=loadLibrary()
  libraryContainer.addView(Button(this).apply{text="無題タイトルを置き換える";isAllCaps=false;setOnClickListener{replaceUntitledLibraryNovels()}})
  if(a.length()==0){libraryContainer.addView(TextView(this).apply{text="まだ生成した小説はありません。";setPadding(8,24,8,24)});return}
  for(i in 0 until a.length()){val n=a.getJSONObject(i);libraryContainer.addView(Button(this).apply{text=novelTitle(n.optString("title",""));isAllCaps=false;setOnClickListener{renderNovelDetail(n)}})}
 }
 private fun renderNovelDetail(n:JSONObject){
  libraryContainer.removeAllViews()
  libraryContainer.addView(Button(this).apply{text="← 一覧へ戻る";setOnClickListener{renderLibrary()}})
  libraryContainer.addView(TextView(this).apply{text=novelTitle(n.optString("title",""));textSize=20f;setPadding(8,20,8,12)})
  libraryContainer.addView(EditText(this).apply{setText(n.optString("body"));textSize=16f;gravity=android.view.Gravity.TOP or android.view.Gravity.START;inputType=android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE;setPadding(12,12,12,20);enableTextEditing(this)})
  libraryContainer.addView(Button(this).apply{text="Lexis投稿";setOnClickListener{loginUploadNovel(novelTitle(n.optString("title","")),n.optString("body"),n.optBoolean("r18",false))}})
  libraryContainer.addView(Button(this).apply{text="ダウンロード";setOnClickListener{downloadNovel=n;startActivityForResult(Intent(Intent.ACTION_CREATE_DOCUMENT).apply{addCategory(Intent.CATEGORY_OPENABLE);type="text/plain";putExtra(Intent.EXTRA_TITLE,n.optString("title","novel").replace(Regex("[\\/:*?\"<>|]"),"_")+".txt")},9001)}})
  libraryContainer.addView(Button(this).apply{text="削除";setOnClickListener{android.app.AlertDialog.Builder(this@NovelGeneratorActivity).setMessage("この小説を削除しますか？").setNegativeButton("キャンセル",null).setPositiveButton("削除"){_,_->deleteLibraryNovel(n.optLong("id"))}.show()}})
 }
 override fun onActivityResult(requestCode:Int,resultCode:Int,data:Intent?){super.onActivityResult(requestCode,resultCode,data);if(requestCode==9001&&resultCode==RESULT_OK){val n=downloadNovel?:return;val uri=data?.data?:return;runCatching{contentResolver.openOutputStream(uri)?.bufferedWriter(Charsets.UTF_8)?.use{w->w.write(n.optString("title"));w.write("\n\n");w.write(n.optString("body"))}}.onSuccess{toast("ダウンロードしました")}.onFailure{toast("保存に失敗しました")};downloadNovel=null}}
 private fun saveDraft(){val x=result.text.toString();if(x.isBlank())return toast("本文がありません");getSharedPreferences("lexis_drafts",MODE_PRIVATE).edit().putString("draft_"+System.currentTimeMillis(),JSONObject().put("title",title.text.toString()).put("body",x).toString()).apply();toast("端末に保存しました")}
 private fun share(){val x=result.text.toString();if(x.isBlank())return toast("本文がありません");startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply{type="text/plain";putExtra(Intent.EXTRA_SUBJECT,title.text.toString());putExtra(Intent.EXTRA_TEXT,x)},"小説を共有"))}
 private fun loginUpload(){loginUploadNovel(title.text.toString().ifBlank{"無題"},result.text.toString(),adult.isChecked)}
 private fun loginUploadNovel(novelTitle:String,novelBody:String,r18:Boolean){if(email.text.isBlank()||password.text.isBlank())return toast("生成画面でLexisのログイン情報を入力してください");if(novelBody.isBlank())return toast("本文がありません");busy(true,"Lexisへ投稿中…");post("https://shosetsu-toukou-site.org/api/auth/login",JSONObject().put("email",email.text.toString().trim()).put("password",password.text.toString()),null){raw->val t=JSONObject(raw).optString("access_token").ifBlank{JSONObject(raw).optString("token")};if(t.isBlank())return@post err("ログイントークンを取得できません");val novel=JSONObject().put("title",novelTitle).put("description","Lexis Androidから投稿").put("age_limit",if(r18)"r18" else "all").put("is_ai_generated",true).put("tag_names",JSONArray());post("https://shosetsu-toukou-site.org/api/novels",novel,t){nr->val id=JSONObject(nr).opt("id")?.toString()?:return@post err("作品IDを取得できません");post("https://shosetsu-toukou-site.org/api/novels/"+id+"/episodes",JSONObject().put("episode_number",1).put("title","第1話").put("body",novelBody).put("tag_names",JSONArray()),t){runOnUiThread{busy(false,"Lexisへのアップロード完了");toast("アップロードしました")}}}}}
 private fun post(url:String,j:JSONObject,t:String?,done:(String)->Unit){val b=Request.Builder().url(url).header("Content-Type","application/json");if(!t.isNullOrBlank())b.header("Authorization","Bearer "+t);b.post(j.toString().toRequestBody("application/json".toMediaType()));client.newCall(b.build()).enqueue(object:Callback{override fun onFailure(c:Call,e:IOException)=err(e.message?:"通信エラー");override fun onResponse(c:Call,r:Response){r.use{val raw=it.body?.string().orEmpty();if(!it.isSuccessful)return err("Lexis API HTTP "+it.code+"\n"+raw.take(400));done(raw)}}})}
 private fun busy(on:Boolean,s:String){runOnUiThread{progress.visibility=if(on)View.VISIBLE else View.GONE;status.text=s}};private fun err(s:String){runOnUiThread{busy(false,s);Toast.makeText(this,s,Toast.LENGTH_LONG).show()}};private fun toast(s:String)=Toast.makeText(this,s,Toast.LENGTH_SHORT).show()
}