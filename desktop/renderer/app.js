const $=id=>document.getElementById(id);
function input(){return{apiKey:$("apiKey").value,model:$("model").value,titleHint:$("titleHint").value,genre:$("genre").value,characters:$("characters").value,tone:$("tone").value,length:$("length").value,r18:$("r18").checked,maxTokens:+$("maxTokens").value,blockCount:+$("blockCount").value,blockMaxTokens:+$("blockMaxTokens").value,blockPlans:$("blockPlans").value.split("\n").map(x=>x.trim()).filter(Boolean),title:$("resultTitle").value,body:$("resultBody").value};}
function show(r){$("resultTitle").value=r.title||"";$("resultBody").value=r.body||"";$("meta").textContent=(r.model||"")+(r.usage?.total_tokens?" / "+r.usage.total_tokens+" tokens":"");$("blocks").innerHTML=(r.blocks||[]).map(b=>"<details><summary>ブロック "+b.index+(b.plan?" — "+b.plan:"")+"</summary><pre></pre></details>").join("");[...$("blocks").querySelectorAll("pre")].forEach((p,i)=>p.textContent=r.blocks[i].body);}
async function busy(fn,msg){$("status").textContent=msg;try{const r=await fn();$("status").textContent="完了";return r}catch(e){$("status").textContent=e.message||String(e);throw e}}
async function refresh(){
  const [history, templates]=await Promise.all([window.lexis.getHistory(),window.lexis.getTemplates()]);
  const h=$("history");h.replaceChildren(new Option("履歴を読み込み",""));
  history.forEach((x,i)=>h.add(new Option(new Date(x.createdAt).toLocaleString()+" "+(x.title||"タイトル未設定"),String(i))));
  h._data=history;h.value="";
  const t=$("templates");t.replaceChildren(new Option("テンプレートを読み込み",""));
  templates.forEach((x,i)=>t.add(new Option(x.name||"テンプレート",String(i))));
  t._data=templates;t.value="";
}

window.lexis.getSettings().then(s=>{$("apiKey").value=s.apiKey||"";$("model").value=s.model||"openrouter/auto";});refresh();
$("saveSettings").onclick=()=>busy(()=>window.lexis.saveSettings({apiKey:$("apiKey").value,model:$("model").value}),"保存中...");
$("loadModels").onclick=async()=>{const ms=await busy(()=>window.lexis.listModels(input()),"モデル取得中...");$("modelList").innerHTML='<option value="">取得したモデルから選択</option>'+ms.map(m=>'<option value="'+m.id+'">'+m.id+"</option>").join("")};
$("modelList").onchange=e=>{if(e.target.value)$("model").value=e.target.value};
$("generate").onclick=async()=>{show(await busy(()=>window.lexis.generateNovel(input()),"生成中..."));await refresh();};
$("generateBlocks").onclick=async()=>{show(await busy(()=>window.lexis.generateBlocks(input()),"ブロック生成中..."));await refresh();};
$("continueNovel").onclick=async()=>{const r=await busy(()=>window.lexis.continueNovel(input()),"続きを生成中...");$("resultBody").value += ($("resultBody").value?"\n\n":"")+r.body;$("meta").textContent=r.model||"";refresh();};
$("saveNovel").onclick=()=>busy(()=>window.lexis.saveNovel({title:$("resultTitle").value,body:$("resultBody").value}),"保存中...");
$("saveTemplate").onclick=async()=>{const name=prompt("テンプレート名","小説設定");if(!name?.trim())return;const {apiKey,body,title,...settings}=input();await busy(()=>window.lexis.saveTemplate({...settings,name:name.trim()}),"テンプレート保存中...");await refresh();$("status").textContent="テンプレートを保存しました";};
$("refreshHistory").onclick=()=>busy(refresh,"履歴・テンプレートを更新中...");
$("history").onchange=e=>{if(e.target.value==="")return;const x=e.target._data?.[Number(e.target.value)];if(x){show(x);$("status").textContent="履歴を読み込みました";}};
$("templates").onchange=e=>{if(e.target.value==="")return;const x=e.target._data?.[Number(e.target.value)];if(!x)return;["model","titleHint","genre","characters","tone","length","maxTokens","blockCount","blockMaxTokens"].forEach(k=>{if(x[k]!=null&&$(k))$(k).value=x[k]});$("r18").checked=!!x.r18;$("blockPlans").value=(x.blockPlans||[]).join("\n");$("status").textContent="テンプレートを読み込みました";};
function renderDraftSearch(){
  const query=$("novelSearch").value.trim().toLocaleLowerCase();
  const all=$("drafts")._all||[];
  const matched=all.filter(x=>!query||(x.title||"").toLocaleLowerCase().includes(query)||(x.body||"").toLocaleLowerCase().includes(query));
  const select=$("drafts");
  select.replaceChildren(new Option("オフライン保存から読み込み",""));
  matched.forEach((x,i)=>select.add(new Option(new Date(x.savedAt).toLocaleString()+" "+(x.title||"タイトル未設定"),String(i))));
  select._data=matched;
  $("novelSearchCount").textContent=matched.length+"件 / "+all.length+"件";
}
async function refreshDrafts(){const d=await window.lexis.listDraftsLocal();$("drafts")._all=d;renderDraftSearch();}
$("novelSearch").addEventListener("input",renderDraftSearch);
$("saveLocal").onclick=async()=>{await busy(()=>window.lexis.saveDraftLocal({title:$("resultTitle").value,body:$("resultBody").value,r18:$("r18").checked}),"オフライン保存中...");refreshDrafts();};
$("drafts").onchange=e=>{const x=e.target._data?.[+e.target.value];if(x){$("resultTitle").value=x.title||"";$("resultBody").value=x.body||"";$("r18").checked=!!x.r18;}};
$("lexisLogin").onclick=()=>busy(()=>window.lexis.lexisLogin({username:$("lexisUsername").value,password:$("lexisPassword").value}),"Lexisログイン中...");
$("uploadLexis").onclick=async()=>{if(!confirm("現在のタイトルと本文をLexisへ新規作品としてアップロードします。よろしいですか？"))return;const r=await busy(()=>window.lexis.uploadToLexis({title:$("resultTitle").value,body:$("resultBody").value,r18:$("r18").checked}),"Lexisへアップロード中...");$("status").textContent="アップロード完了: "+r.url;};
refreshDrafts();

$("updateApp").onclick=()=>busy(()=>window.lexis.updateApp(),"最新版のダウンロードページを開いています...");
$("uninstallApp").onclick=async()=>{if(!confirm("Lexis Novel Desktopをアンインストールしますか？\nオフライン保存や設定も不要なら、アンインストール後にアプリデータを手動削除できます。"))return;await busy(()=>window.lexis.uninstallApp(),"アンインストーラーを起動しています...");};

$("shareXTxt").onclick=async()=>{const r=await busy(()=>window.lexis.shareXTxt({title:$("resultTitle").value,body:$("resultBody").value}),"TXTを保存してXを開いています...");$("status").textContent=r.canceled?"共有をキャンセルしました":"TXTを保存してXを開きました。Xへのファイル添付は手動で行ってください。";};
