function addBlockPlan(value=""){const n=$("blockPlanBoxes").children.length+1;const w=document.createElement("label");w.className="block-plan";w.textContent="ブロック "+n;const t=document.createElement("textarea");t.rows=4;t.placeholder="このブロックで書いてほしい内容";t.value=value;w.appendChild(t);$("blockPlanBoxes").appendChild(w);$("blockCount").value=$("blockPlanBoxes").children.length;}
function getBlockPlans(){return [...$("blockPlanBoxes").querySelectorAll("textarea")].map(x=>x.value.trim());}
function setBlockPlans(plans){$("blockPlanBoxes").innerHTML="";(plans&&plans.length?plans:["","","",""]).forEach(addBlockPlan);}
const $=id=>document.getElementById(id);
function input(){return{apiKey:$("apiKey").value,model:$("model").value,titleHint:$("titleHint").value,genre:$("genre").value,characters:$("characters").value,tone:$("tone").value,length:$("length").value,r18:$("r18").checked,maxTokens:+$("maxTokens").value,blockCount:+$("blockCount").value,blockMaxTokens:+$("blockMaxTokens").value,blockPlans:getBlockPlans(),title:$("resultTitle").value,body:$("resultBody").value};}
function show(r){$("resultTitle").value=r.title||"";$("resultBody").value=r.body||"";$("meta").textContent=(r.model||"")+(r.usage?.total_tokens?" / "+r.usage.total_tokens+" tokens":"");$("blocks").innerHTML=(r.blocks||[]).map(b=>"<details><summary>ブロック "+b.index+(b.plan?" — "+b.plan:"")+"</summary><pre></pre></details>").join("");[...$("blocks").querySelectorAll("pre")].forEach((p,i)=>p.textContent=r.blocks[i].body);}
async function busy(fn,msg){$("status").textContent=msg;try{const r=await fn();$("status").textContent="完了";return r}catch(e){$("status").textContent=e.message||String(e);throw e}}
async function refresh(){const h=await window.lexis.getHistory();$("history").innerHTML='<option value="">履歴を読み込み</option>'+h.map((x,i)=>'<option value="'+i+'">'+new Date(x.createdAt).toLocaleString()+" "+x.title+"</option>").join("");$("history")._data=h;const t=await window.lexis.getTemplates();$("templates").innerHTML='<option value="">テンプレートを読み込み</option>'+t.map((x,i)=>'<option value="'+i+'">'+(x.name||"テンプレート")+"</option>").join("");$("templates")._data=t;}
window.lexis.getSettings().then(s=>{$("apiKey").value=s.apiKey||"";$("model").value=s.model||"openrouter/auto";});setBlockPlans();$("addBlockPlan").onclick=()=>addBlockPlan();refresh();
$("saveSettings").onclick=()=>busy(()=>window.lexis.saveSettings({apiKey:$("apiKey").value,model:$("model").value}),"保存中...");
$("loadModels").onclick=async()=>{const ms=await busy(()=>window.lexis.listModels(input()),"モデル取得中...");$("modelList").innerHTML='<option value="">取得したモデルから選択</option>'+ms.map(m=>'<option value="'+m.id+'">'+m.id+"</option>").join("")};
$("modelList").onchange=e=>{if(e.target.value)$("model").value=e.target.value};
$("generate").onclick=async()=>show(await busy(()=>window.lexis.generateNovel(input()),"生成中..."));
$("generateBlocks").onclick=async()=>show(await busy(()=>window.lexis.generateBlocks(input()),"ブロック生成中..."));
$("continueNovel").onclick=async()=>{const r=await busy(()=>window.lexis.continueNovel(input()),"続きを生成中...");$("resultBody").value += ($("resultBody").value?"\n\n":"")+r.body;$("meta").textContent=r.model||"";refresh();};
$("saveNovel").onclick=()=>busy(()=>window.lexis.saveNovel({title:$("resultTitle").value,body:$("resultBody").value}),"保存中...");
$("saveTemplate").onclick=async()=>{const name=prompt("テンプレート名","小説設定");if(!name)return;await busy(()=>window.lexis.saveTemplate({...input(),apiKey:undefined,body:undefined,title:undefined,name}),"テンプレート保存中...");refresh();};
$("refreshHistory").onclick=refresh;
$("history").onchange=e=>{const x=e.target._data?.[+e.target.value];if(x)show(x)};
$("templates").onchange=e=>{const x=e.target._data?.[+e.target.value];if(!x)return;["model","titleHint","genre","characters","tone","length","maxTokens","blockCount","blockMaxTokens"].forEach(k=>{if(x[k]!=null&&$(k))$(k).value=x[k]});$("r18").checked=!!x.r18;setBlockPlans(x.blockPlans||[]);};
async function refreshDrafts(){const d=await window.lexis.listDraftsLocal();$("drafts").innerHTML='<option value="">オフライン保存から読み込み</option>'+d.map((x,i)=>'<option value="'+i+'">'+new Date(x.savedAt).toLocaleString()+" "+x.title+"</option>").join("");$("drafts")._data=d;}
$("saveLocal").onclick=async()=>{await busy(()=>window.lexis.saveDraftLocal({title:$("resultTitle").value,body:$("resultBody").value,r18:$("r18").checked}),"オフライン保存中...");refreshDrafts();};
$("drafts").onchange=e=>{const x=e.target._data?.[+e.target.value];if(x){$("resultTitle").value=x.title||"";$("resultBody").value=x.body||"";$("r18").checked=!!x.r18;}};
$("lexisLogin").onclick=()=>busy(()=>window.lexis.lexisLogin({username:$("lexisUsername").value,password:$("lexisPassword").value}),"Lexisログイン中...");
$("uploadLexis").onclick=async()=>{if(!confirm("現在のタイトルと本文をLexisへ新規作品としてアップロードします。よろしいですか？"))return;const r=await busy(()=>window.lexis.uploadToLexis({title:$("resultTitle").value,body:$("resultBody").value,r18:$("r18").checked}),"Lexisへアップロード中...");$("status").textContent="アップロード完了: "+r.url;};
refreshDrafts();

$("updateApp").onclick=()=>busy(()=>window.lexis.updateApp(),"最新版のダウンロードページを開いています...");
$("uninstallApp").onclick=async()=>{if(!confirm("Lexis Novel Desktopをアンインストールしますか？\nオフライン保存や設定も不要なら、アンインストール後にアプリデータを手動削除できます。"))return;await busy(()=>window.lexis.uninstallApp(),"アンインストーラーを起動しています...");};
