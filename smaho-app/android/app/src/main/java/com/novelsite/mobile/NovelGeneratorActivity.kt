package com.novelsite.mobile
import android.content.Intent
import android.os.Bundle
import android.view.View
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
 private val client=OkHttpClient.Builder().connectTimeout(30,TimeUnit.SECONDS).readTimeout(180,TimeUnit.SECONDS).build()
 private lateinit var key:EditText; private lateinit var model:Spinner; private lateinit var title:EditText; private lateinit var genre:EditText
 private lateinit var chars:EditText; private lateinit var mood:EditText; private lateinit var prompt:EditText; private lateinit var adult:CheckBox
 private lateinit var blocks:EditText; private lateinit var tokens:EditText; private lateinit var result:EditText; private lateinit var progress:ProgressBar; private lateinit var status:TextView
 private lateinit var email:EditText; private lateinit var password:EditText; private lateinit var blockPromptContainer:LinearLayout; private lateinit var retryCount:EditText
 private val prefs by lazy{val mk=MasterKey.Builder(this).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build();EncryptedSharedPreferences.create(this,"lexis_secure",mk,EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM)}
 override fun onCreate(b:Bundle?){super.onCreate(b);setContentView(R.layout.activity_novel_generator)
  key=findViewById(R.id.apiKey);model=findViewById(R.id.modelSpinner);title=findViewById(R.id.titleInput);genre=findViewById(R.id.genreInput);chars=findViewById(R.id.charactersInput);mood=findViewById(R.id.moodInput);prompt=findViewById(R.id.instructionInput);adult=findViewById(R.id.r18Check);blocks=findViewById(R.id.blockCount);tokens=findViewById(R.id.maxTokens);result=findViewById(R.id.resultText);progress=findViewById(R.id.progress);status=findViewById(R.id.status);email=findViewById(R.id.lexisEmail);password=findViewById(R.id.lexisPassword);blockPromptContainer=findViewById(R.id.blockPromptContainer);retryCount=findViewById(R.id.retryCount)
  key.setText(prefs.getString("openrouter_key","")); setModels(listOf("openrouter/auto")); addBlockPrompt(); addBlockPrompt(); addBlockPrompt()
  findViewById<Button>(R.id.addBlockPrompt).setOnClickListener{addBlockPrompt()}
  findViewById<Button>(R.id.saveApiKey).setOnClickListener{prefs.edit().putString("openrouter_key",key.text.toString().trim()).apply();toast("APIキーを保存しました")}
  findViewById<Button>(R.id.loadModels).setOnClickListener{loadModels()};findViewById<Button>(R.id.generate).setOnClickListener{generate(false)};findViewById<Button>(R.id.generateBlocks).setOnClickListener{generate(true)}
  findViewById<Button>(R.id.continueButton).setOnClickListener{continueStory()};findViewById<Button>(R.id.saveDraft).setOnClickListener{saveDraft()};findViewById<Button>(R.id.shareText).setOnClickListener{share()};findViewById<Button>(R.id.uploadLexis).setOnClickListener{loginUpload()}
 }
 private fun addBlockPrompt(){
  val e=EditText(this);e.hint="ブロック "+(blockPromptContainer.childCount+1)+" の指示";e.minLines=3;e.gravity=android.view.Gravity.TOP;e.inputType=android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE or android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES;e.setPadding(24,18,24,18)
  val lp=LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT,LinearLayout.LayoutParams.WRAP_CONTENT);lp.setMargins(0,8,0,8);e.layoutParams=lp;blockPromptContainer.addView(e);blocks.setText(blockPromptContainer.childCount.toString())
  e.setOnEditorActionListener{_,_,_->if(e===blockPromptContainer.getChildAt(blockPromptContainer.childCount-1)){addBlockPrompt();true}else false}
 }
 private fun blockPrompts(): List<String> = (0 until blockPromptContainer.childCount).map { index -> (blockPromptContainer.getChildAt(index) as EditText).text.toString().trim() }
 private fun k()=key.text.toString().trim();private fun m()=model.selectedItem?.toString()?:"openrouter/auto";private fun limit()=(tokens.text.toString().toIntOrNull()?:2000).coerceIn(512,8192)
 private fun retries()=(retryCount.text.toString().toIntOrNull()?:20).coerceIn(0,100)
 private fun base():String{val a=if(adult.isChecked)"\n成人向け表現を許可。ただし登場人物は全員18歳以上で、合意のある成人同士の関係のみ。" else "";return "日本語の小説を書いてください。\nタイトル: "+title.text+"\nジャンル: "+genre.text+"\n登場人物: "+chars.text+"\n雰囲気・文体: "+mood.text+"\n指示・あらすじ: "+prompt.text+a+"\n説明ではなく小説本文を出力してください。"}
 private fun setModels(x:List<String>){model.adapter=ArrayAdapter(this,android.R.layout.simple_spinner_dropdown_item,x)}
 private fun loadModels(){if(k().isBlank())return toast("APIキーを入力してください");busy(true,"モデル取得中…");val q=Request.Builder().url("https://openrouter.ai/api/v1/models").header("Authorization","Bearer "+k()).build();client.newCall(q).enqueue(object:Callback{override fun onFailure(c:Call,e:IOException)=err(e.message?:"通信エラー");override fun onResponse(c:Call,r:Response){r.use{if(!it.isSuccessful)return err("モデル取得失敗 HTTP "+it.code);val a=JSONObject(it.body?.string().orEmpty()).optJSONArray("data")?:JSONArray();val x=(0 until a.length()).mapNotNull{i->a.optJSONObject(i)?.optString("id")?.takeIf{v->v.isNotBlank()}}.sorted();runOnUiThread{setModels(x.ifEmpty{listOf("openrouter/auto")});busy(false,x.size.toString()+"モデル取得")}}}})}
 private fun generate(multi:Boolean){if(k().isBlank())return toast("APIキーを入力してください");if(prompt.text.isBlank())return toast("生成指示を入力してください");if(!multi){call(base()){result.setText(it);busy(false,"生成完了")};return};val filled=blockPrompts();val n=maxOf((blocks.text.toString().toIntOrNull()?:filled.size).coerceIn(2,12),filled.size.coerceAtMost(12));result.setText("");block(1,n,"",filled)}
 private fun block(i:Int,n:Int,old:String,instructions:List<String>){busy(true,i.toString()+" / "+n+" ブロック生成中…");val context=if(old.isBlank())"" else "\n\nここまでの本文:\n"+old.takeLast(12000);val specific=instructions.getOrNull(i-1).orEmpty();val direction=if(specific.isBlank())"" else "\nこのブロック固有の指示: "+specific;call(base()+"\n\n全"+n+"ブロック中の第"+i+"ブロックを書いてください。前後を自然につないでください。"+direction+context){p->val all=if(old.isBlank())p else old+"\n\n"+p;result.setText(all);if(i<n)block(i+1,n,all,instructions)else busy(false,"ブロック生成完了")}}
 private fun continueStory(){val old=result.text.toString();if(old.isBlank())return toast("本文がありません");call(base()+"\n\n以下の本文の直後から続きを書いてください。\n\n"+old.takeLast(14000)){p->result.setText(old+"\n\n"+p);busy(false,"続きを生成しました")}}
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
    if(text.isBlank())return retryOrFail(p,done,attempt,maxRetries,"AIから空の応答が返りました。")
    runOnUiThread{done(text)}
   }}
  })
 }
 private fun retryOrFail(p:String,done:(String)->Unit,attempt:Int,maxRetries:Int,message:String){
  if(attempt>=maxRetries)return err(message+"（再試行上限 "+maxRetries+" 回）")
  runOnUiThread{status.text="再試行 "+(attempt+1)+" / "+maxRetries+"…"}
  android.os.Handler(mainLooper).postDelayed({callAttempt(p,done,attempt+1,maxRetries)},minOf(5000L,500L+attempt*250L))
 }
 private fun saveDraft(){val x=result.text.toString();if(x.isBlank())return toast("本文がありません");getSharedPreferences("lexis_drafts",MODE_PRIVATE).edit().putString("draft_"+System.currentTimeMillis(),JSONObject().put("title",title.text.toString()).put("body",x).toString()).apply();toast("端末に保存しました")}
 private fun share(){val x=result.text.toString();if(x.isBlank())return toast("本文がありません");startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply{type="text/plain";putExtra(Intent.EXTRA_SUBJECT,title.text.toString());putExtra(Intent.EXTRA_TEXT,x)},"小説を共有"))}
 private fun loginUpload(){if(email.text.isBlank()||password.text.isBlank())return toast("Lexisのログイン情報を入力してください");if(result.text.isBlank())return toast("本文がありません");post("https://shosetsu-toukou-site.org/api/auth/login",JSONObject().put("email",email.text.toString().trim()).put("password",password.text.toString()),null){raw->val t=JSONObject(raw).optString("access_token").ifBlank{JSONObject(raw).optString("token")};if(t.isBlank())return@post err("ログイントークンを取得できません");val novel=JSONObject().put("title",title.text.toString().ifBlank{"無題"}).put("description",prompt.text.toString()).put("age_limit",if(adult.isChecked)"r18" else "all").put("is_ai_generated",true).put("tag_names",JSONArray());post("https://shosetsu-toukou-site.org/api/novels",novel,t){nr->val id=JSONObject(nr).opt("id")?.toString()?:return@post err("作品IDを取得できません");post("https://shosetsu-toukou-site.org/api/novels/"+id+"/episodes",JSONObject().put("episode_number",1).put("title","第1話").put("body",result.text.toString()).put("tag_names",JSONArray()),t){runOnUiThread{busy(false,"Lexisへのアップロード完了");toast("アップロードしました")}}}}}
 private fun post(url:String,j:JSONObject,t:String?,done:(String)->Unit){val b=Request.Builder().url(url).header("Content-Type","application/json");if(!t.isNullOrBlank())b.header("Authorization","Bearer "+t);b.post(j.toString().toRequestBody("application/json".toMediaType()));client.newCall(b.build()).enqueue(object:Callback{override fun onFailure(c:Call,e:IOException)=err(e.message?:"通信エラー");override fun onResponse(c:Call,r:Response){r.use{val raw=it.body?.string().orEmpty();if(!it.isSuccessful)return err("Lexis API HTTP "+it.code+"\n"+raw.take(400));done(raw)}}})}
 private fun busy(on:Boolean,s:String){runOnUiThread{progress.visibility=if(on)View.VISIBLE else View.GONE;status.text=s}};private fun err(s:String){runOnUiThread{busy(false,s);Toast.makeText(this,s,Toast.LENGTH_LONG).show()}};private fun toast(s:String)=Toast.makeText(this,s,Toast.LENGTH_SHORT).show()
}