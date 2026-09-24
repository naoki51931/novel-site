function addBlockPlan(value=""){const n=$("blockPlanBoxes").children.length+1;const w=document.createElement("label");w.className="block-plan";w.textContent="ブロック "+n;const t=document.createElement("textarea");t.rows=4;t.placeholder="このブロックで書いてほしい内容";t.value=value;w.appendChild(t);$("blockPlanBoxes").appendChild(w);$("blockCount").value=$("blockPlanBoxes").children.length;}
function getBlockPlans(){return [...$("blockPlanBoxes").querySelectorAll("textarea")].map(x=>x.value.trim());}
function setBlockPlans(plans){$("blockPlanBoxes").innerHTML="";(plans&&plans.length?plans:["","","",""]).forEach(addBlockPlan);}
const $=id=>document.getElementById(id);
function input(){return{apiKey:$("apiKey").value,model:$("model").value,titleHint:$("titleHint").value,genre:$("genre").value,characters:$("characters").value,tone:$("tone").value,length:$("length").value,r18:$("r18").checked,maxTokens:+$("maxTokens").value,blockCount:+$("blockCount").value,blockMaxTokens:+$("blockMaxTokens").value,retryCount:+$("retryCount").value,blockPlans:getBlockPlans(),title:$("resultTitle").value,body:$("resultBody").value};}
function show(r){$("resultTitle").value=r.title||"";$("resultBody").value=r.body||"";$("meta").textContent=(r.model||"")+(r.usage?.total_tokens?" / "+r.usage.total_tokens+" tokens":"");$("blocks").innerHTML=(r.blocks||[]).map(b=>"<details><summary>ブロック "+b.index+(b.plan?" — "+b.plan:"")+"</summary><pre></pre></details>").join("");[...$("blocks").querySelectorAll("pre")].forEach((p,i)=>p.textContent=r.blocks[i].body);}
async function busy(fn,msg){$("status").textContent=msg;try{const r=await fn();$("status").textContent="完了";return r}catch(e){$("status").textContent=e.message||String(e);throw e}}
async function refresh(){const h=await window.lexis.getHistory();$("history").innerHTML='<option value="">履歴を読み込み</option>'+h.map((x,i)=>'<option value="'+i+'">'+new Date(x.createdAt).toLocaleString()+" "+x.title+"</option>").join("");$("history")._data=h;const t=await window.lexis.getTemplates();$("templates").innerHTML='<option value="">テンプレートを読み込み</option>'+t.map((x,i)=>'<option value="'+i+'">'+(x.name||"テンプレート")+"</option>").join("");$("templates")._data=t;}
window.lexis.getSettings().then(s=>{$("apiKey").value=s.apiKey||"";$("model").value=s.model||"openrouter/auto";});setBlockPlans();$("addBlockPlan").onclick=()=>addBlockPlan();refresh();
$("saveSettings").onclick=()=>busy(()=>window.lexis.saveSettings({apiKey:$("apiKey").value,model:$("model").value}),"保存中...");
$("loadModels").onclick=async()=>{const ms=await busy(()=>window.lexis.listModels(input()),"モデル取得中...");$("modelList").innerHTML='<option value="">取得したモデルから選択</option>'+ms.map(m=>'<option value="'+m.id+'">'+m.id+"</option>").join("")};
$("modelList").onchange=e=>{if(e.target.value)$("model").value=e.target.value};
$("generate").onclick=async()=>{const r=await busy(()=>window.lexis.generateNovel(input()),"生成中...");show(r);await window.lexis.saveLibraryNovel({title:r.title,body:r.body,r18:$("r18").checked});};
$("generateBlocks").onclick=async()=>{const r=await busy(()=>window.lexis.generateBlocks(input()),"ブロック生成中...");show(r);await window.lexis.saveLibraryNovel({title:r.title,body:r.body,r18:$("r18").checked});};
$("continueNovel").onclick=async()=>{const r=await busy(()=>window.lexis.continueNovel(input()),"続きを生成中...");$("resultBody").value += ($("resultBody").value?"\n\n":"")+r.body;$("meta").textContent=r.model||"";await window.lexis.saveLibraryNovel({title:$("resultTitle").value,body:$("resultBody").value,r18:$("r18").checked});refresh();};
$("saveNovel").onclick=()=>busy(()=>window.lexis.saveNovel({title:$("resultTitle").value,body:$("resultBody").value}),"保存中...");
$("saveTemplate").onclick=async()=>{const name=prompt("テンプレート名","小説設定");if(!name)return;await busy(()=>window.lexis.saveTemplate({...input(),apiKey:undefined,body:undefined,title:undefined,name}),"テンプレート保存中...");refresh();};
$("refreshHistory").onclick=refresh;
$("history").onchange=e=>{const x=e.target._data?.[+e.target.value];if(x)show(x)};
$("templates").onchange=e=>{const x=e.target._data?.[+e.target.value];if(!x)return;["model","titleHint","genre","characters","tone","length","maxTokens","blockCount","blockMaxTokens","retryCount"].forEach(k=>{if(x[k]!=null&&$(k))$(k).value=x[k]});$("r18").checked=!!x.r18;setBlockPlans(x.blockPlans||[]);};
async function refreshDrafts(){const d=await window.lexis.listDraftsLocal();$("drafts").innerHTML='<option value="">オフライン保存から読み込み</option>'+d.map((x,i)=>'<option value="'+i+'">'+new Date(x.savedAt).toLocaleString()+" "+x.title+"</option>").join("");$("drafts")._data=d;}
$("saveLocal").onclick=async()=>{await busy(()=>window.lexis.saveDraftLocal({title:$("resultTitle").value,body:$("resultBody").value,r18:$("r18").checked}),"オフライン保存中...");refreshDrafts();};
$("drafts").onchange=e=>{const x=e.target._data?.[+e.target.value];if(x){$("resultTitle").value=x.title||"";$("resultBody").value=x.body||"";$("r18").checked=!!x.r18;}};
$("lexisLogin").onclick=()=>busy(()=>window.lexis.lexisLogin({username:$("lexisUsername").value,password:$("lexisPassword").value}),"Lexisログイン中...");
$("uploadLexis").onclick=async()=>{if(!confirm("現在のタイトルと本文をLexisへ新規作品としてアップロードします。よろしいですか？"))return;const r=await busy(()=>window.lexis.uploadToLexis({title:$("resultTitle").value,body:$("resultBody").value,r18:$("r18").checked}),"Lexisへアップロード中...");$("status").textContent="アップロード完了: "+r.url;};
refreshDrafts();

$("updateApp").onclick=()=>busy(()=>window.lexis.updateApp(),"最新版のダウンロードページを開いています...");
$("uninstallApp").onclick=async()=>{if(!confirm("Lexis Novel Desktopをアンインストールしますか？\nオフライン保存や設定も不要なら、アンインストール後にアプリデータを手動削除できます。"))return;await busy(()=>window.lexis.uninstallApp(),"アンインストーラーを起動しています...");};

let selectedLibraryNovel=null;
async function loadLibrary(){
 const novels=await window.lexis.listLibraryNovels();
 $("libraryList").innerHTML="";
 if(!novels.length){$("libraryList").textContent="まだ生成した小説はありません。";return;}
 novels.forEach(n=>{const b=document.createElement("button");b.className="library-item";b.style.display="block";b.style.width="100%";b.style.margin="8px 0";b.style.textAlign="left";b.textContent=(n.title||"タイトル未設定")+"　"+new Date(n.savedAt).toLocaleString();b.onclick=()=>openLibraryNovel(n);$("libraryList").appendChild(b);});
}
function setLibraryEditing(on){$("libraryTitleInput").disabled=!on;$("libraryBody").disabled=!on;$("libraryEdit").style.display=on?"none":"";$("librarySaveEdit").style.display=on?"":"none";$("libraryCancelEdit").style.display=on?"":"none";}
function openLibraryNovel(n){selectedLibraryNovel=n;$("libraryList").style.display="none";$("libraryDetail").style.display="block";$("libraryTitleInput").value=n.title||"Lexis生成小説";$("libraryBody").value=n.body||"";$("libraryStatus").textContent="";setLibraryEditing(false);}
$("replaceUntitledTitles").onclick=async()=>{const r=await window.lexis.replaceUntitledLibraryNovels("Lexis生成小説");$("libraryStatus").textContent=r.changed+"件のタイトルを「"+r.title+"」に置き換えました。";await loadLibrary();};
$("navGenerate").onclick=()=>{$("generatorView").style.display="block";$("libraryView").style.display="none";};
$("navLibrary").onclick=async()=>{$("generatorView").style.display="none";$("libraryView").style.display="block";$("libraryDetail").style.display="none";$("libraryList").style.display="block";await loadLibrary();};
$("libraryBack").onclick=()=>{$("libraryDetail").style.display="none";$("libraryList").style.display="block";selectedLibraryNovel=null;};
$("libraryEdit").onclick=()=>{if(selectedLibraryNovel)setLibraryEditing(true);};
$("libraryCancelEdit").onclick=()=>{if(!selectedLibraryNovel)return;$("libraryTitleInput").value=selectedLibraryNovel.title||"Lexis生成小説";$("libraryBody").value=selectedLibraryNovel.body||"";setLibraryEditing(false);};
$("librarySaveEdit").onclick=async()=>{if(!selectedLibraryNovel)return;const saved=await window.lexis.saveLibraryNovel({id:selectedLibraryNovel.id,title:$("libraryTitleInput").value,body:$("libraryBody").value,r18:!!selectedLibraryNovel.r18});selectedLibraryNovel={...selectedLibraryNovel,...saved};$("libraryTitleInput").value=saved.title;$("libraryStatus").textContent="編集内容を保存しました。";setLibraryEditing(false);};
$("libraryDownload").onclick=async()=>{if(!selectedLibraryNovel)return;await window.lexis.saveNovel({title:$("libraryTitleInput").value,body:$("libraryBody").value});$("libraryStatus").textContent="ダウンロード保存しました。";};
$("libraryDelete").onclick=async()=>{if(!selectedLibraryNovel||!confirm("この小説を一覧から削除しますか？"))return;await window.lexis.deleteLibraryNovel(selectedLibraryNovel.id);selectedLibraryNovel=null;$("libraryDetail").style.display="none";$("libraryList").style.display="block";await loadLibrary();};
$("libraryUpload").onclick=async()=>{if(!selectedLibraryNovel)return;if(!confirm("この小説をLexisへ投稿しますか？"))return;try{const r=await window.lexis.uploadToLexis({title:$("libraryTitleInput").value,body:$("libraryBody").value,r18:!!selectedLibraryNovel.r18});$("libraryStatus").textContent="Lexis投稿完了: "+r.url;}catch(e){$("libraryStatus").textContent=e.message||String(e);}};
