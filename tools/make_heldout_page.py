"""Builds evals/label_heldout.html: a self-contained page for a human to label the golden 50.
Nothing is sent anywhere; answers live in the browser and export as CSV."""
import csv, json, sys
rows = list(csv.DictReader(open("evals/heldout_to_label.csv", encoding="utf-8", newline="")))
data = json.dumps([{k: r[k] for k in ("review_id", "review_text", "review_rating")} for r in rows]).replace("</", "<\/")
html = r'''<!doctype html><html><head><meta charset="utf-8"><title>Held-out 30 labeling</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font:15px/1.45 system-ui,sans-serif;max-width:920px;margin:0 auto;padding:16px;background:#fafafa;color:#222}
.card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:16px;margin:12px 0}
.text{font-size:17px;white-space:pre-wrap;background:#f3f6fb;padding:12px;border-radius:6px;user-select:text}
label{display:block;margin-top:10px;font-weight:600} select,input,textarea{font:inherit;padding:6px;width:100%;box-sizing:border-box}
.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.help{font-weight:400;color:#555;font-size:13px}
button{font:inherit;padding:8px 14px;margin:4px 4px 4px 0;cursor:pointer}details{margin:8px 0}
.bar{position:sticky;top:0;background:#fafafa;padding:8px 0;border-bottom:1px solid #ddd;z-index:2}
td,th{padding:3px 8px;text-align:left;vertical-align:top;font-size:13px}
</style></head><body>
<div class="bar"><b id="prog"></b> <button onclick="go(-1)">&larr; Prev</button><button onclick="go(1)">Next &rarr;</button>
<button onclick="exportCsv()">Download CSV</button> <span class="help">Autosaves in this browser.</span></div>
<details><summary><b>Label definitions (click to open)</b></summary>
<table><tr><th>topic</th><th>meaning</th></tr>
<tr><td>access</td><td>login, signup, password, account access</td></tr>
<tr><td>usability</td><td>navigation, controls, layout, queue/playlist management, ad interruptions</td></tr>
<tr><td>playback</td><td>playback failure, crashes, lag, connection failures, audio quality, resource use</td></tr>
<tr><td>downloads</td><td>downloading, saved music, offline listening, disappearing downloads</td></tr>
<tr><td>catalog</td><td>missing songs/artists, search/discovery, recommendations, lyrics</td></tr>
<tr><td>billing</td><td>price, charges, subscriptions, paywalls, premium entitlement; premium-only controls. Just mentioning a paid plan is NOT billing.</td></tr>
<tr><td>support</td><td>contacting support, support response</td></tr>
<tr><td>other</td><td>general praise/criticism, unrelated, or no specific topic</td></tr></table>
<p><b>Topic rule:</b> pick the problem with the highest severity; on a tie, the first one mentioned. For praise, the first specific praised feature (general praise = other).</p>
<table><tr><th>intent (first that applies)</th><th>meaning</th></tr>
<tr><td>cancellation</td><td>explicitly leaving, uninstalling, cancelling, or threatening to</td></tr>
<tr><td>complaint</td><td>negative experience (including mixed praise + criticism)</td></tr>
<tr><td>request</td><td>wants a change, no reported failure</td></tr>
<tr><td>praise</td><td>positive only</td></tr>
<tr><td>unclear</td><td>meaningless/unrelated, or bare boycott slogans</td></tr></table>
<table><tr><th>severity</th><th>meaning</th></tr>
<tr><td>1</td><td>no problem: praise, neutral/unclear, or a pure feature request</td></tr>
<tr><td>2</td><td>dislike, generic criticism, minor annoyance, cosmetic; no real loss of function</td></tr>
<tr><td>3</td><td>degraded/restricted function; some use or workaround remains</td></tr>
<tr><td>4</td><td>a core task clearly blocked (can't log in, can't play music)</td></tr>
<tr><td>5</td><td>explicit serious financial, privacy or data harm. Expensive plan, a crash, or angry language alone is NOT enough.</td></tr></table>
<p>Do NOT judge severity from stars or anger. Cancellation intent alone does not raise severity. If context is missing, tick "needs review" instead of guessing.</p></details>
<div id="app"></div>
<script>
const D=__DATA__;let i=0;const KEY="heldout30_v1";
let A=JSON.parse(localStorage.getItem(KEY)||"{}");
const T=["access","usability","playback","downloads","catalog","billing","support","other"],
I=["cancellation","complaint","request","praise","unclear"];
function opt(a,v){return '<option value="">--</option>'+a.map(x=>`<option ${x==v?"selected":""}>${x}</option>`).join("")}
function render(){const d=D[i],a=A[d.review_id]||{};
document.getElementById("prog").textContent=`Review ${i+1}/50 - ${Object.values(A).filter(x=>x.topic&&x.intent&&x.severity&&x.sentiment!==undefined&&x.sentiment!=="").length} done`;
document.getElementById("app").innerHTML=`<div class="card"><div class="text" id="txt">${esc(d.review_text)}</div>
<div class="help">(Star rating is hidden on purpose so it can't bias you.)</div>
<div class="row"><div><label>Topic</label><select onchange="s('topic',this.value)">${opt(T,a.topic)}</select></div>
<div><label>Intent</label><select onchange="s('intent',this.value)">${opt(I,a.intent)}</select></div></div>
<div class="row"><div><label>Severity (1-5)</label><select onchange="s('severity',this.value)">${opt([1,2,3,4,5],a.severity)}</select></div>
<div><label>Sentiment <span class="help">-1 very negative ... 0 neutral ... 1 very positive</span></label>
<select onchange="s('sentiment',this.value)">${opt([-1,-0.5,0,0.5,1],a.sentiment)}</select></div></div>
<label>Entities <span class="help">specific features/things named, comma separated (e.g. "ads, shuffle"); blank if none</span></label>
<input value="${esc(a.entities||"")}" oninput="s('entities',this.value)">
<label>Evidence quote <span class="help">exact words from the review that justify your labels. Select text above, then click the button.</span></label>
<textarea rows="2" id="q" oninput="s('evidence_quote',this.value)">${esc(a.evidence_quote||"")}</textarea>
<button onclick="useSel()">Use selected text</button><button onclick="useAll()">Use whole review</button>
<label><input type="checkbox" style="width:auto" ${a.needs_review?"checked":""} onchange="s('needs_review',this.checked)"> Needs review (ambiguous / missing context)</label>
</div>`}
function esc(x){return String(x).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
function s(k,v){const id=D[i].review_id;A[id]=A[id]||{};A[id][k]=v;localStorage.setItem(KEY,JSON.stringify(A));
document.getElementById("prog").textContent=document.getElementById("prog").textContent}
function useSel(){const t=String(getSelection());if(t){document.getElementById("q").value=t;s("evidence_quote",t)}}
function useAll(){const t=D[i].review_text;document.getElementById("q").value=t;s("evidence_quote",t)}
function go(n){i=Math.max(0,Math.min(49,i+n));render()}
function q(x){return '"'+String(x??"").replace(/"/g,'""')+'"'}
function exportCsv(){const h=["review_id","topic","intent","sentiment","severity","entities","evidence_quote","needs_review"];
const L=[h.join(",")];D.forEach(d=>{const a=A[d.review_id]||{};L.push([d.review_id,a.topic,a.intent,a.sentiment,a.severity,a.entities,a.evidence_quote,a.needs_review?"true":"false"].map(q).join(","))});
const b=new Blob([L.join("\n")],{type:"text/csv"}),u=URL.createObjectURL(b),e=document.createElement("a");e.href=u;e.download="heldout_labeled.csv";e.click()}
render();
</script></body></html>'''.replace("__DATA__", data)
open("evals/label_heldout.html", "w", encoding="utf-8").write(html)
print("ok", len(rows))
