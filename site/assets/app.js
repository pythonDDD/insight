/* insight: no third-party scripts, trackers, accounts or trading. */
"use strict";
(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const url = s => { try { const u = new URL(s); return u.protocol === "https:" ? esc(u.href) : "#"; } catch { return "#"; } };
  const link = (href, text, cls = "") => `<a class="${cls}" href="${url(href)}" target="_blank" rel="noopener noreferrer">${esc(text)} ↗</a>`;
  const fmt = (v, n = 2) => Number.isFinite(v) ? v.toLocaleString("ja-JP", {maximumFractionDigits:n,minimumFractionDigits:n}) : "—";
  const sign = (v, n = 2) => Number.isFinite(v) ? `${v > 0 ? "+" : ""}${fmt(v,n)}` : "—";
  const pc = v => Number.isFinite(v) ? fmt(v * 100, v < .01 || v > .99 ? 1 : 0) : "—";
  const color = v => !Number.isFinite(v) || v === 0 ? "neutral" : v > 0 ? "positive" : "negative";
  const date = (s, detail = false) => s ? new Intl.DateTimeFormat("ja-JP", {timeZone:"Asia/Tokyo",month:"2-digit",day:"2-digit",...(detail ? {hour:"2-digit",minute:"2-digit",hour12:false} : {})}).format(new Date(s)) : "未取得";
  const timeOnly = s => s ? new Intl.DateTimeFormat("ja-JP", {timeZone:"Asia/Tokyo",hour:"2-digit",minute:"2-digit",hour12:false}).format(new Date(s)) : "—";
  const compact = n => n >= 1e6 ? `$${fmt(n/1e6,1)}M` : n >= 1e3 ? `$${fmt(n/1e3,1)}K` : `$${fmt(n,0)}`;
  const viewNames = {overview:"市場の現在地",outlook:"1週間の見通し",prediction:"予測市場を読む",news:"ニュースと予定",learn:"なるほど、市場の教室",method:"データと読み方"};
  const groups = {all:"すべて",equity:"世界の株式",rates:"金利",crypto:"暗号資産",commodity:"商品",fx:"為替",tech:"AI・テック"};
  let data = window.__INSIGHT__?.snapshot, learning = window.__INSIGHT__?.learn;
  const state = {view:"overview", days:1,sigma:1,newsSource:"all",newsHours:0,asset:"sp500",group:"all",topic:"all",weekOnly:true,search:"",lesson:null};
  let refreshing = false;
  let chartSequence = 0;

  const asset = id => data.assets.find(a=>a.id===id);
  function actualStale(q) { return !q?.observedAt || (Date.now()-new Date(q.observedAt).getTime())/36e5 > (q.group==="crypto" ? 30 : 96); }
  function price(q,v=q?.price) { return !q || !Number.isFinite(v) ? "—" : fmt(v, q.unit==="yield" ? 3 : q.id==="eurusd" ? 4 : q.price < 10 ? 4 : 2) + (q.unit==="yield" ? "%" : ""); }
  function movement(q) { return q?.unit==="yield" ? `${sign(q.changeBps,1)} bp` : `${sign(q?.changePct)}%`; }
  function epochDays(days,crypto) {
    if (crypto) return days;
    let count=0; const origin = new Date(new Date(data.generatedAt).getTime()+9*36e5);
    for(let i=1;i<=days;i++){const d=new Date(origin);d.setUTCDate(origin.getUTCDate()+i);if(d.getUTCDay()!==0&&d.getUTCDay()!==6) count++;}
    return count;
  }

  function range(q, days=state.days) {
    if(!q || !q.sigma || !q.price || actualStale(q) || q.status!=="ok") return null;
    const n=epochDays(days,q.group==="crypto"), sigma=q.sigma*Math.sqrt(n)*state.sigma;
    return q.unit==="yield" ? {lo:q.price-sigma/100,hi:q.price+sigma/100,n,sigma} : {lo:q.price*Math.exp(-sigma/100),hi:q.price*Math.exp(sigma/100),n,sigma};
  }
  function sourceBadge(name, href, via="") {
    return `<div class="source-credit">${link(href,`出典：${name}`,"source-badge")}${via?`<span class="source-via">${esc(via)}経由</span>`:""}</div>`;
  }
  function momentumMeter(value, measure="価格", compact=false) {
    const valid=Number.isFinite(value), v=valid?Math.max(-100,Math.min(100,value)):0;
    const tone=!valid||Math.abs(v)<18?"neutral":v>0?"positive":"negative";
    const label=!valid?"評価を保留":v>=18?"上向きの勢い":v<=-18?"下向きの勢い":"中立圏・方向感が弱い";
    const attrs=valid?`role="meter" aria-label="${esc(measure)}の独自勢いスコア" aria-valuemin="-100" aria-valuemax="100" aria-valuenow="${v}" aria-valuetext="${v}、${label}。確率ではありません"`:'';
    if(compact)return `<div class="compact-meter ${tone}" ${attrs}><strong>${valid?sign(v,0):"—"}</strong><div class="compact-track">${valid?`<i style="left:${(v+100)/2}%"></i>`:""}</div><div class="compact-scale"><span>−100</span><span>0</span><span>＋100</span></div><small>${esc(label)}</small></div>`;
    const point=(score,r=85)=>{const a=Math.PI+(score+100)/200*Math.PI;return [120+Math.cos(a)*r,104+Math.sin(a)*r];};
    const arc=(a,b)=>{const p=point(a),q=point(b);return `M${p[0]},${p[1]} A85,85 0 0 1 ${q[0]},${q[1]}`;};
    const needle=point(v,64);
    const ticks=[-100,-50,0,50,100].map(t=>{const a=point(t,96),b=point(t,104);return `<path d="M${a} L${b}" stroke="#b8c6d8" stroke-width="2"/>`;}).join("");
    return `<div class="momentum-meter ${tone}" ${attrs}><div class="meter-heading"><span>勢いスコア</span><span class="badge">独自指標</span></div><svg viewBox="0 0 240 116" aria-hidden="true"><path d="${arc(-100,-18)}" stroke="#ee8e98"/><path d="${arc(-18,18)}" stroke="#8ea5c2"/><path d="${arc(18,100)}" stroke="#62d7bd"/>${ticks}${valid?`<line x1="120" y1="104" x2="${needle[0]}" y2="${needle[1]}" stroke="#f8fbff" stroke-width="4" stroke-linecap="round"/><circle cx="120" cy="104" r="7" fill="#f8fbff"/>`:""}</svg><div class="meter-scale"><span>−100<br>下向き</span><span>0<br>中立</span><span>＋100<br>上向き</span></div><div class="meter-value">${valid?sign(v,0):"—"}</div><strong class="meter-label">${esc(label)}</strong><p class="meter-note">${measure==="利回り"?"利回りの方向。債券価格は通常、逆方向。":"値動きの方向と強さを表示。"}<br>上昇確率・予想騰落率ではありません。</p></div>`;
  }
  function scoreGuide() {
    return `<details class="score-guide"><summary>−100〜＋100は、何を表す数字？ <span>独自の「勢い」の読み方</span></summary><div class="score-guide-grid"><div><strong class="negative">−100〜−18</strong><span>下向きの勢い</span></div><div><strong class="neutral">−17〜＋17</strong><span>中立圏・方向感が弱い</span></div><div><strong class="positive">＋18〜＋100</strong><span>上向きの勢い</span></div></div><p>過去5取引日と前日の値動きを、それぞれ普段の変動幅で割ってから合成しています。絶対値が大きいほど、普段に比べて一方向への動きが強かったことを表します。0付近でも、銘柄の上昇と下落が打ち消し合っている場合があります。</p><p><b>＋70は「70%の確率で上がる」という意味ではありません。</b> ±100は表示上の上限、±18は独自の判定基準です。見通しの期間を切り替えても、足元のスコアは共通です。カテゴリは取得できた銘柄の単純平均です。</p><p class="source-note">価格データ：Yahoo Finance ／ スコア計算：insight</p></details>`;
  }
  function sigmaSwitch() {return `<div class="segmented" role="group" aria-label="振れ幅の倍率">${[1,2].map(n=>`<button data-sigma="${n}" class="${state.sigma===n?"active":""}" aria-pressed="${state.sigma===n}">±${n}σ</button>`).join("")}</div>`;}

  function spark(q) {
    const hs=(q.history||[]).slice(-22).map(h=>h.v);
    if(hs.length<2) return "";
    let min=Math.min(...hs),max=Math.max(...hs),span=max-min||1;
    const points=hs.map((v,i)=>`${i/(hs.length-1)*92},${30-(v-min)/span*26}`).join(" ");
    return `<svg class="spark" viewBox="0 0 92 33" role="img" aria-label="直近の日次価格の推移"><polyline points="${points}" fill="none" stroke="${hs.at(-1)>=hs[0]?"#65d6bd":"#ff9297"}" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
  }
  function statusStrip() {
    const age=(Date.now()-new Date(data.generatedAt).getTime())/36e5;
    const stale=age>2.5, bad=data.sources.filter(s=>s.status!=="ok").length;
    return `<div class="status-strip ${stale||bad?"warn":""}"><i class="status-dot"></i><b>${stale?"更新が遅れています":bad?"一部データの取得に失敗": "公開データ取得済み"}</b><span>取得処理 ${date(data.generatedAt,true)} JST</span><span>${data.assets.filter(q=>q.status==="ok").length}銘柄 · ${data.predictions.length}予測市場</span><a href="#method">${stale?"最終データと取得状況を確認":"毎時更新・データの状態"} ↗</a></div>`;
  }
  function horizonSwitch() {return `<div class="segmented" role="group" aria-label="見通しの期間">${[1,3,7].map(n=>`<button data-days="${n}" class="${state.days===n?"active":""}" aria-pressed="${state.days===n}">${n===1?"明日":n===3?"3日先":"1週間"}</button>`).join("")}</div>`;}
  function ticker(q) {return `<button class="ticker ${state.asset===q.id?"active":""}" data-asset="${q.id}" aria-label="${esc(q.name)}のグラフを表示"><div class="ticker-head"><span>${esc(q.name)}</span><span class="asset-symbol">${esc(q.symbol)}</span></div><div class="ticker-value mono">${price(q)}</div><div class="ticker-bottom"><span class="ticker-change ${color(q.unit==="yield"?q.changeBps:q.changePct)}">${movement(q)}<small>前日比</small></span>${spark(q)}</div><div class="ticker-asof">${q.status!=="ok"?"前回データ · ":""}${actualStale(q)?"古い観測値 · ":""}${date(q.observedAt,true)} JST</div><div class="ticker-source">出典：Yahoo Finance</div></button>`;}
  function chart(q, showRange=true) {
    if(!q || !q.price || (q.history||[]).length<2) return `<div class="empty">価格を取得できていません。次の取得結果を待って表示します。</div>`;
    const hist=q.history.slice(-25), r=showRange?range(q):null;
    const vals=hist.map(h=>h.v).concat([q.price,...(r?[r.lo,r.hi]:[])]);
    let min=Math.min(...vals),max=Math.max(...vals),span=max-min||max*.01||1;min-=span*.15;max+=span*.15;
    const narrow=window.innerWidth&&window.innerWidth<720;
    const W=narrow?380:680,H=250,left=0,right=narrow?292:570,top=20,bottom=204,end=showRange?right*.75:right;
    const gradientId=`priceFill-${++chartSequence}`;
    const y=v=>top+(max-v)/(max-min)*(bottom-top);
    const pts=hist.map((h,i)=>[left+i/(hist.length-1)*(end-left),y(h.v)]);
    pts[pts.length-1]=[end,y(q.price)];
    const path=pts.map((p,i)=>`${i?"L":"M"}${p[0].toFixed(2)},${p[1].toFixed(2)}`).join(" ");
    const grid=Array.from({length:4},(_,i)=>{const v=min+(max-min)*i/3, yy=y(v);return `<line x1="0" y1="${yy}" x2="${right}" y2="${yy}" stroke="#37485c" stroke-dasharray="3 5"/><text x="${right+9}" y="${yy+5}" fill="#c4cfdd" font-size="14" font-weight="600">${esc(fmt(v,q.unit==="yield"?2:q.price<10?3:0))}</text>`;}).join("");
    let band="";
    if(r){
      const edge=direction=>Array.from({length:25},(_,i)=>{const f=i/24,vol=direction*q.sigma*state.sigma*Math.sqrt(r.n*f);const p=q.unit==="yield"?q.price+vol/100:q.price*Math.exp(vol/100);return [end+(right-end)*f,y(p)];});
      const hi=edge(1),lo=edge(-1),poly=hi.concat([...lo].reverse()).map(p=>p.join(",")).join(" ");
      band=`<polygon points="${poly}" fill="#9abcf3" fill-opacity=".2"/><polyline points="${hi.map(p=>p.join(",")).join(" ")}" fill="none" stroke="#a8c9ff" stroke-width="2" stroke-dasharray="5 4"/><polyline points="${lo.map(p=>p.join(",")).join(" ")}" fill="none" stroke="#a8c9ff" stroke-width="2" stroke-dasharray="5 4"/><line x1="${end}" x2="${end}" y1="10" y2="${bottom}" stroke="#94a8bf" stroke-dasharray="3 5"/>`;
    }
    return `<div class="chart-container" style="aspect-ratio:${W}/${H}"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${esc(q.name)}の過去25観測値${r?`と${state.days}日先、±${state.sigma}σ相当の参考バンド`:""}"><defs><linearGradient id="${gradientId}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#65d6bd" stop-opacity=".16"/><stop offset="100%" stop-color="#65d6bd" stop-opacity="0"/></linearGradient></defs>${grid}<path d="${path} L${end},${bottom} L0,${bottom} Z" fill="url(#${gradientId})"/><path d="${path}" fill="none" stroke="#65d6bd" stroke-width="2.5" stroke-linejoin="round"/>${band}<circle cx="${end}" cy="${y(q.price)}" r="4" fill="#c7f58a"/><text x="0" y="236" fill="#c4cfdd" font-size="14">${date(new Date(hist[0].t*1000).toISOString())}</text><text x="${end}" y="236" text-anchor="middle" fill="#d1f59f" font-size="13" font-weight="700">最終価格</text>${r?`<text x="${right}" y="236" text-anchor="end" fill="#b5d0ff" font-size="13" font-weight="700">${state.days}日先</text>`:""}</svg></div>`;
  }

  function chartPanel(q) {
    const r=range(q), target=date(new Date(new Date(data.generatedAt).getTime()+state.days*864e5).toISOString());
    return `<div class="panel" id="marketChart"><div class="panel-top"><div><div class="panel-label">価格と、過去の変動から考える幅</div><h2>${esc(q.name)} <span class="badge">${esc(q.unit==="index"?"指数":q.currency)}</span></h2></div>${horizonSwitch()}</div><div class="chart-price mono"><strong>${price(q)}</strong><span class="${color(q.unit==="yield"?q.changeBps:q.changePct)}">${movement(q)} <small>前日比</small></span></div><div class="chart-source-row">${sourceBadge(q.source||"Yahoo Finance",q.sourceUrl)}<span>価格の観測 ${date(q.observedAt,true)} JST</span></div><div class="band-toolbar"><strong>振れ幅バンド <span>±${state.sigma}σ相当</span></strong>${sigmaSwitch()}</div>${chart(q)}<div class="chart-key"><span>実際の価格推移</span><span>${state.days}日先までの±${state.sigma}σ相当</span></div><div class="range-callout"><div><b>${state.days}日先（${target}）・±${state.sigma}σ相当</b><span>過去の変動から計算した参考範囲</span></div><strong class="mono">${r?`${price(q,r.lo)} 〜 ${price(q,r.hi)}`:"計算材料なし"}</strong></div><div class="band-facts"><div><span>幅の計算に使う期間</span><strong>${r?`${r.n}${q.group==="crypto"?"暦日":"営業日（概算）"}`:"—"}</strong></div><div><span>σを求めたデータ</span><strong>直近${q.sampleSize||0}日次変化</strong></div><div><span>日次の1σ</span><strong>${Number.isFinite(q.sigma)?`${fmt(q.sigma,2)} ${q.unit==="yield"?"bp":"%（対数変化）"}`:"—"}</strong></div></div><details class="band-explainer"><summary>σ（シグマ）と、この幅の読み方</summary><p>σは、値動きのばらつきの大きさです。日次のσに「期間の日数の平方根」と倍率${state.sigma}を掛けています。価格は対数変化、金利はbpで計算し、中心は最終価格に固定しています。</p><p><b>この帯に入る確率が68%・95%だと保証するものではありません。</b>過去のばらつきから広げた目安で、上昇・下落を予言する線ではありません。</p><p>${q.group==="crypto"?"暗号資産は土日を含む暦日で計算。":"土日を除く概算。各国の祝日・取引時間は未調整。"}${q.unit==="futures"?"先物は限月交代による価格の段差に注意。":""}</p></details><p class="source-note">出典：Yahoo Finance ／ バンドの計算：insight</p></div>`;
  }

  function storyPanel() {
    const oil=asset("oil"),rate=asset("us10y"),nas=asset("nasdaq");
    return `<section class="panel story-panel"><div class="panel-label">TODAY'S CONNECTION</div><div class="panel-top"><h2>今日の数字を、線でつなぐ。</h2><span class="badge green">3つの視点</span></div><p class="source-note">数値の出典：Yahoo Finance ／ 解説：insight</p><p class="story-intro">見るべきなのは「上がった・下がった」の先。<strong>原油、金利、企業の利益</strong>をつなぐと、ニュースの意味が見えてきます。</p><div class="cause-row"><span class="cause-number">01</span><div class="cause-copy"><strong>原油は、経済の「燃料代」</strong><p>WTI ${movement(oil)}。上昇が続けば企業の費用と物価に圧力。</p></div></div><div class="cause-row"><span class="cause-number">02</span><div class="cause-copy"><strong>金利は、お金を借りる「レンタル料」</strong><p>米10年債 ${price(rate)}。金利が上がると将来の利益を厳しく評価しやすい。</p></div></div><div class="cause-row"><span class="cause-number">03</span><div class="cause-copy"><strong>株価は、将来の利益の「期待値」</strong><p>NASDAQ ${movement(nas)}。AI企業の決算が、期待に追いつくかが焦点。</p></div></div><div class="counter"><strong>でも、決めつけない。</strong>金利上昇が景気の強さを表す場合は、企業利益の改善が株価を支えることもあります。数字の理由を確認しましょう。</div><button class="outline-button" data-lesson="rates">このつながりを、たとえ話で理解する <span>↗</span></button></section>`;
  }
  function outlookCard(o) {
    const h=o.horizons.find(h=>h.days===state.days);
    return `<article class="outlook-card"><div class="card-title"><h3>${esc(o.title)}</h3><span class="badge">${o.id==="rates"?"利回りの方向":"条件付きの見通し"}</span></div>${momentumMeter(o.score,o.measure)}<p class="outlook-copy">${esc(h.text)}</p><p class="source-note">価格：Yahoo Finance ／ 計算：insight</p><div class="card-foot"><span>観測 ${esc(o.coverage)}</span><button data-outlook="${o.id}">根拠・関連情報を読む ↗</button></div></article>`;
  }

  function humanMarket(question) {
    const months={January:1,February:2,March:3,April:4,May:5,June:6,July:7,August:8,September:9,October:10,November:11,December:12};
    const jpDate=s=>s.replace(/(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2})(?:, (\d{4}))?/,(_,m,d,y)=>`${y?y+"年":""}${months[m]}月${d}日`);
    let m=question.match(/^(US|Israel) x Iran ceasefire continues through (.+)\?$/);
    if(m)return `${m[1]==="US"?"米国":"イスラエル"}とイランの停戦は${jpDate(m[2])}まで続く？`;
    m=question.match(/^Will the Fed (decrease|increase) interest rates by (\d+)(\+?) bps after the (\w+) (\d{4}) meeting\?$/);
    if(m&&months[m[4]])return `${m[5]}年${months[m[4]]}月のFOMC後、政策金利は${fmt(+m[2]/100,2)}ポイント${m[3]?"以上":""}${m[1]==="decrease"?"下がる":"上がる"}？`;
    m=question.match(/^Will there be no change in Fed interest rates after the (\w+) (\d{4}) meeting\?$/);
    if(m&&months[m[1]])return `${m[2]}年${months[m[1]]}月のFOMC後、政策金利は据え置き？`;
    m=question.match(/^Will the price of (Bitcoin|Ethereum) be above (\$[\d,]+) on (.+)\?$/);
    if(m)return `${jpDate(m[3])}の${m[1]}価格は${m[2]}を上回る？`;
    m=question.match(/^(Bitcoin|Ethereum) Up or Down on (.+)\?$/);
    if(m)return `${jpDate(m[2])}の${m[1]}価格は上昇、それとも下落？`;
    return question;
  }
  function pmMini(m) {
    return `<div class="mini-pm"><div><h3>${link(m.url,humanMarket(m.question))}</h3><p><b>出典：Polymarket</b><br>${esc(m.category)} · 判定期限 ${date(m.endAt,true)} JST</p></div><div class="pm-number">${m.probability===null?"複数":pc(m.probability)}<small>${m.probability===null?"":"%"}</small><span>${m.probability===null?"回答別の市場":"Yes価格由来"}</span></div></div>`;
  }
  function eventRow(e, full=false) {
    const exact=e.timePrecision!=="date";
    return `<article class="event"><div class="event-date">${exact?date(e.at):esc(e.sourceDate.slice(5).replace("-","/"))}<small>${exact?`${timeOnly(e.at)} JST`:"米国日付"}</small></div><div><h3>${esc(e.title)}</h3><p>${esc(e.explanation)}</p>${sourceBadge(e.sourceName,e.url)}${full?`<details><summary>時刻・確認日について</summary>${esc(e.timeNote)}<br>確認：${date(e.verifiedAt,true)} JST</details>`:""}</div></article>`;
  }
  function overview() {
    const keyIds=["sp500","nasdaq","us10y","bitcoin","gold","oil"];
    const pm=data.predictions.filter(m=>m.withinWeek).slice(0,3);
    return `<section class="hero"><div><div class="eyebrow">MAKE SENSE OF THE MARKETS</div><h1>世界のいまを、<br>明日の見通しにつなげる。</h1><p>政治、経済、戦争、AI。そのニュースは、なぜ市場を動かすのか。<br>事実と予想を分けながら、明日から1週間を見渡します。</p></div><div class="hero-date"><strong>${date(data.windowStart)} — ${date(data.windowEnd)}</strong><span>観測から考える、次の1週間 / JST</span></div></section>${statusStrip()}<div class="ticker-grid">${keyIds.map(id=>ticker(asset(id))).join("")}</div><div class="columns">${chartPanel(asset(state.asset))}${storyPanel()}</div><div class="section-heading"><h2>資産ごとの見通し<span class="sub">いまの勢いと、次の分岐点</span></h2>${horizonSwitch()}</div>${scoreGuide()}<div class="outlook-grid">${data.outlooks.slice(0,6).map(outlookCard).join("")}</div><div class="two-columns"><section class="panel"><div class="panel-top"><div><div class="panel-label">PREDICTION MARKET</div><h2>市場参加者は、どう見ている？</h2></div><a href="#prediction" class="text-link">すべて ↗</a></div>${pm.length?pm.map(pmMini).join(""):empty("対象期間の市場を取得できていません。") }<p class="micro">Polymarketのイベントに対する価格。資産の値上がり確率ではありません。各条件・期限は元ページで確認。</p></section><section class="panel"><div class="panel-top"><div><div class="panel-label">NEXT CATALYSTS</div><h2>次の1週間、ここを見る。</h2></div><a href="#news" class="text-link">予定を見る ↗</a></div>${data.events.length?data.events.slice(0,3).map(e=>eventRow(e)).join(""):empty("対象期間の確認済み予定はありません。予定がないことを意味しません。")}</section></div><div class="section-heading"><h2>市場を詳しく見る</h2><span class="text-link">銘柄を選ぶと、価格推移を表示</span></div>${groupFilters()}${marketTable()}`;
  }
  function groupFilters() {return `<div class="filters">${Object.entries(groups).map(([id,label])=>`<button class="chip ${state.group===id?"active":""}" data-group="${id}" aria-pressed="${state.group===id}">${label}</button>`).join("")}</div>`;}
  function marketTable() {
    const rows=data.assets.filter(q=>state.group==="all"||q.group===state.group);
    return `<div class="table-wrap"><table class="market-table"><thead><tr><th>銘柄・指標</th><th>現在値</th><th>前日比</th><th>足元の勢い</th><th>価格の観測時刻 / JST</th><th>出典</th></tr></thead><tbody>${rows.map(q=>`<tr><td><button data-detail-asset="${q.id}">${esc(q.name)}<small>${esc(q.region)}</small></button></td><td class="mono">${price(q)}<small>${q.unit==="index"?"指数ポイント":q.unit==="yield"?"利回り":esc(q.currency)}</small></td><td class="mono ${color(q.unit==="yield"?q.changeBps:q.changePct)}">${movement(q)}</td><td>${momentumMeter(q.status==="ok"&&!actualStale(q)?q.score:null,q.unit==="yield"?"利回り":"価格",true)}</td><td>${date(q.observedAt,true)}<small>${q.status!=="ok"?"今回取得失敗 / ":""}${actualStale(q)?"古い観測値":"配信遅延・休場に注意"}</small></td><td>${link(q.sourceUrl,"Yahoo Finance")}</td></tr>`).join("")}</tbody></table></div>`;
  }
  function pageIntro(eyebrow,title,body) {return `<div class="page-intro"><div class="eyebrow">${esc(eyebrow)}</div><h1>${esc(title)}</h1><p>${esc(body)}</p></div>`;}
  function outlookFull(o) {
    const h=o.horizons.find(h=>h.days===state.days), related=(o.newsIds||[]).map(id=>data.news.find(n=>n.id===id)).filter(Boolean).slice(0,2), markets=(o.marketIds||[]).map(id=>data.predictions.find(m=>m.id===id)).filter(Boolean).slice(0,1);
    return `<article class="outlook-full"><div><span class="badge">${esc(o.measure)}の見方</span><h2 style="margin-top:10px">${esc(o.title)}</h2>${momentumMeter(o.score,o.measure)}<p class="source-note">価格：Yahoo Finance<br>計算：insight ／ 観測 ${esc(o.coverage)}</p></div><div><p class="horizon-copy">${esc(h.text)}</p><ul class="fact-list">${o.facts.map(f=>`<li><span class="badge blue">観測</span> ${link(f.url,f.text)}<small>出典：Yahoo Finance · ${date(f.at,true)} JST</small></li>`).join("")||"<li>新鮮な観測データが足りないため、方向の評価を保留しています。</li>"}</ul><div class="scenario-boxes"><div class="scenario-box"><b>この条件なら</b>${esc(o.upside)}</div><div class="scenario-box"><b>反対の結果になる条件</b>${esc(o.downside)}</div></div>${related.length||markets.length?`<div class="related-evidence"><h3>併せて読む、関連情報</h3><p class="source-note">以下は関連テーマの情報です。勢いスコアには加算していません。</p>${related.map(n=>`<div>${sourceBadge(n.source,n.url,n.via)}<p>${link(n.url,n.title)}</p></div>`).join("")}${markets.map(m=>`<div>${sourceBadge("Polymarket",m.url)}<p>${link(m.url,humanMarket(m.question))}</p></div>`).join("")}</div>`:""}<div class="card-foot"><span>条件付き解説：insight</span><button data-lesson="${data.topics[o.topic]?.lesson||"rates"}">しくみを学ぶ ↗</button></div></div></article>`;
  }

  function outlookView() {return `${pageIntro("CONDITIONAL OUTLOOK","「どう動く？」を、条件から考える。","ひとつの未来を断言せず、現在の勢い・変化のきっかけ・反対の条件をセットで整理します。期間の切替で着目点が変わります。")}${statusStrip()}${scoreGuide()}<div class="notice info">「上向き・下向き」は過去の価格から計算した勢いです。未来の上昇確率ではありません。金利欄は<b>利回り</b>の方向で、通常、債券価格は反対に動きます。</div><div class="section-heading"><h2>${state.days===1?"明日まで":state.days===3?"3日先":"1週間先"}の観察ポイント</h2>${horizonSwitch()}</div>${data.outlooks.map(outlookFull).join("")}${simulator()}`;}
  function pmGuide(m) {
    if(/ceasefire|hormuz|iran|israel/i.test(m.question)) return "停戦・航路の安全は原油の供給不安につながります。ただし『確率が高い』だけでは、新たな株高材料かどうかは分かりません。";
    if(/fed|rate/i.test(m.question)) return "金利判断は株・債券・為替に波及。ただし織り込まれた予想通りなら、値動きは小さいこともあります。";
    if(/bitcoin|ethereum/i.test(m.question)) return "価格水準・判定時刻に関する市場です。『一度タッチする』と『終値で超える』は別の条件です。";
    if(/nvidia|meta|tesla|microsoft|alphabet|openai/i.test(m.question)) return "企業や技術に関する見込み。企業利益への影響と、株価にすでに織り込まれた期待を分けて考えます。";
    return "政治・経済イベントの見込みです。結果が決まっても、その後の政策実施や資産価格の方向は別問題です。";
  }
  function pmCard(m) {return `<article class="pm-card">${sourceBadge("Polymarket",m.url)}<div><span class="badge ${m.withinWeek?"green":"blue"}">${m.withinWeek?"対象の1週間以内":"背景材料・期限は1週間より先"}</span></div><h3>${link(m.url,humanMarket(m.question))}</h3>${humanMarket(m.question)!==m.question?`<details class="micro"><summary>原文の質問</summary>${esc(m.question)}</details>`:""}${m.probability!==null?`<div class="pm-number">${pc(m.probability)}<small>%</small><span>Yes の市場価格から読む目安</span></div><div class="pm-progress"><span style="width:${m.probability*100}%"></span></div>`:`<div>${m.outcomes.map(o=>`<div class="pm-details"><span>${esc(o.label)}</span><b>${pc(o.probability)}%</b></div>`).join("")}</div>`}<div class="pm-details"><span>24h 出来高<b>${compact(m.volume24h)}</b></span><span>流動性<b>${compact(m.liquidity)}</b></span><span>スプレッド<b>${Number.isFinite(m.spread)?fmt(m.spread*100,1)+"¢":"未取得"}</b></span><span>前回取得比<b class="${color(m.changePp)}">${Number.isFinite(m.changePp)?sign(m.changePp,1)+" pt":"比較履歴なし"}</b></span></div>${m.lowLiquidity?`<p class="pm-warning">板が薄い、または価格差が大きい市場です。</p>`:""}<div class="pm-guide">${esc(pmGuide(m))}</div><div class="pm-end">判定期限 ${date(m.endAt,true)} JST<br>取得 ${date(m.fetchedAt,true)} JST${m.status!=="ok"?" · 前回値":""}${m.comparisonAt?`<br>比較元 ${date(m.comparisonAt,true)} JST`:""}<br>条件・決済ルールは原文で確認 ↗</div></article>`;}
  function topicFilters(type) {const topics=Object.entries(data.topics);return `<div class="filters"><button class="chip ${state.topic==="all"?"active":""}" data-topic="all">すべて</button>${topics.map(([id,t])=>`<button class="chip ${state.topic===id?"active":""}" data-topic="${id}">${esc(t.name)}</button>`).join("")}<input type="search" class="search-box" id="searchInput" placeholder="${type==="pm"?"市場の質問を検索":"ニュースの見出しを検索"}" value="${esc(state.search)}" aria-label="表示内容を検索"></div>`;}
  function filteredPM() {return data.predictions.filter(m=>(!state.weekOnly||m.withinWeek)&&(state.topic==="all"||m.topic===state.topic)&&m.question.toLowerCase().includes(state.search.toLowerCase()));}
  function predictionView() {return `${pageIntro("PROBABILITY, NOT CERTAINTY","予測市場の「何％」を、正しく読む。","Polymarketで実際に取引されるイベントの価格を表示します。誰かの予言ではなく、参加者が今どのように見込んでいるかの観測です。")}${statusStrip()}<div class="notice"><b>90% ≠ 株価が90%の確率で上がる。</b> 表示値は、その質問に対する市場価格の目安です。期限、条件、取引の薄さで意味が変わります。価格は中間値または約定値のため、合計が100%と一致しない場合もあります。</div><div class="section-heading"><h2>注目イベント</h2><label class="toggle-label"><input type="checkbox" id="weekOnly" ${state.weekOnly?"checked":""}>期限が1週間以内のみ</label></div>${topicFilters("pm")}<div class="pm-grid" id="pmResults">${filteredPM().map(pmCard).join("")||empty("この条件の市場は取得できていません。条件を変更してください。")}</div><p class="micro">出来高上位から抽出した一部の市場です。最低流動性$1,000・24h出来高$100。テーマごとの上限あり。スポーツ・短時間の賭け市場を除外。1週間より先のイベントは背景情報として区別します。</p>`;}
  function newsCard(n) {const t=data.topics[n.topic]||data.topics.economy;const recent=Date.now()-new Date(n.publishedAt).getTime()<36e5;return `<article class="news-card"><div class="news-meta">${sourceBadge(n.source,n.url,n.via)}<span>${date(n.publishedAt,true)} JST</span></div><div class="news-tags"><span class="badge">${esc(t.name)}</span><span class="badge ${n.tier==="一次資料"?"blue":""}">${esc(n.tier)}</span>${recent?'<span class="badge green">1時間以内</span>':""}</div><h3 style="margin-top:12px">${link(n.url,n.title)}</h3><div class="news-question"><small>この記事を読むときの問い</small>${esc(t.question)}</div><div class="causal-chain">${t.chain.map((s,i)=>`${i?"<b>→</b>":""}<span>${esc(s)}</span>`).join("")}</div><p class="news-limit">${esc(t.caution)}<br>経路はテーマ別の一般的な説明です。記事本文の分析ではありません。</p><div class="card-foot"><span>${n.status==="cached"?"前回取得の見出し":n.via?"見出しのみ取得・有料記事あり":"RSS見出し・本文は元記事へ"}</span><button data-lesson="${t.lesson}">しくみを学ぶ ↗</button></div></article>`;}

  function filteredNews() {return data.news.filter(n=>(state.topic==="all"||n.topic===state.topic)&&(state.newsSource==="all"||n.source===state.newsSource)&&(!state.newsHours||Date.now()-new Date(n.publishedAt).getTime()<=state.newsHours*36e5)&&`${n.title} ${n.source}`.toLowerCase().includes(state.search.toLowerCase()));}
  function newsControls() {const publishers=[...new Set(data.news.map(n=>n.source))].sort((a,b)=>a.localeCompare(b,"ja"));return `<div class="news-controls"><label>媒体で絞る <select id="newsSource" aria-label="ニュースの出典"><option value="all">すべての媒体</option>${publishers.map(n=>`<option value="${esc(n)}" ${state.newsSource===n?"selected":""}>${esc(n)}</option>`).join("")}</select></label><div class="segmented" role="group" aria-label="ニュースの期間"><button data-news-hours="0" class="${!state.newsHours?"active":""}" aria-pressed="${!state.newsHours}">直近7日</button><button data-news-hours="24" class="${state.newsHours===24?"active":""}" aria-pressed="${state.newsHours===24}">24時間以内</button></div></div>`;}
  function socialPanel() {return `<section class="social-panel"><div><div class="panel-label">公式アカウントで速報を確認</div><h2>X / Twitter</h2><p>Xの投稿は現在、自動収集していません。最新の投稿は各公式アカウントで確認できます。</p></div><div class="social-links">${[["NHKニュース","nhk_news"],["日本経済新聞","nikkei"],["ロイター日本語","ReutersJapan"],["共同通信","kyodo_official"]].map(([name,account])=>link(`https://x.com/${account}`,`${name} @${account}`,"social-link")).join("")}</div></section>`;}

  function newsView() {return `${pageIntro("NEWS & CATALYSTS","情報の出どころから、次の分岐点を読む。","日本経済新聞・NHKなどの報道と、中央銀行の公式発表を出典付きで確認。取得は毎時で、リアルタイムの速報配信ではありません。")}${statusStrip()}${socialPanel()}<div class="section-heading"><h2>新着ニュース</h2><span class="text-link">新しい順 · 最大100件</span></div>${newsControls()}${topicFilters("news")}<div class="news-grid" id="newsResults">${filteredNews().map(newsCard).join("")||empty("この条件のニュースはありません。")}</div><section class="panel calendar-panel"><div class="panel-top"><div><div class="panel-label">THE WEEK AHEAD / JST</div><h2>確認済みの予定</h2></div><span class="badge">日程は変更される場合があります</span></div>${data.events.map(e=>eventRow(e,true)).join("")||empty("対象期間の確認済み予定はありません。予定がないという意味ではありません。") }<p class="micro">米国BLSカレンダーは毎時再取得。企業決算・日本CPI・FOMCは公式資料を確認した個別予定で、期限経過後に自動で除外します。すべての予定を網羅するものではありません。</p></section>`;}

  function simulator() {return `<section class="simulator"><div class="eyebrow">WHAT IF LAB / 学習用</div><h2>もしも、金利と原油が動いたら？</h2><p class="panel-subtitle">他の条件が同じ場合の、一般的な影響を考える実験。価格を予測する計算機ではありません。</p><div class="sim-controls"><label>米長期金利の変化<output id="rateOutput">0 bp</output><input id="rateSlider" type="range" min="-50" max="50" step="5" value="0" aria-label="米長期金利の変化、ベーシスポイント"></label><label>原油の変化（供給要因と仮定）<output id="oilOutput">0%</output><input id="oilSlider" type="range" min="-20" max="20" step="2" value="0" aria-label="供給要因による原油価格の変化、パーセント"></label></div><div class="sim-result" id="simResult"></div><p class="micro">景気の強さで原油・金利が上がる場合には、この説明通りにならないことがあります。変化量から株価の変化率や確率への換算はしません。</p></section>`;}
  function updateSim() {if(!$("#simResult"))return;const r=+$("#rateSlider").value,o=+$("#oilSlider").value;$("#rateOutput").textContent=`${sign(r,0)} bp`;$("#oilOutput").textContent=`${sign(o,0)}%`;const texts=[r>0?"借入費用や将来利益の割引率が上がり、成長株には逆風になりやすい。":r<0?"借入費用や割引率が下がり、成長株の評価を支えやすい。ただし不況が理由なら別。":"金利だけからの追加の圧力は仮定していません。",o>0?"供給不足なら原油高で輸送・製造費が増え、利益や家計を圧迫しやすい。":o<0?"供給回復なら燃料費が下がり、輸送・製造や家計を助けやすい。":"原油供給からの追加の変化は仮定していません。",r>0?"物価予想が同じなら実質金利も上昇。利息を生まない金の魅力は相対的に下がりやすい。":r<0?"物価予想が同じなら実質金利も低下。金には追い風になりやすい。":"名目金利が同じでも、物価予想と安全資産需要で金は動きます。"];
    $("#simResult").innerHTML=texts.map((t,i)=>`<div><strong>${["株式・AI企業","企業のコスト・物価","金と実質金利"][i]}</strong>${t}</div>`).join("");}
  function learnView() {return `${pageIntro("THE MARKET CLASSROOM","わかると、ニュースの見え方が変わる。","難しい用語は、身近なたとえから。一歩ずつ因果関係をたどり、反対のケースまで考えてみましょう。")}<div class="learn-grid">${learning.topics.map((t,i)=>`<button class="lesson-card" data-lesson="${t.id}"><div class="lesson-no">0${i+1}</div><div class="eyebrow">${esc(t.eyebrow)}</div><h2>${esc(t.title)}</h2><p>${esc(t.summary)}</p><span class="lesson-link">たとえ → しくみ → 確認クイズ ↗</span></button>`).join("")}</div>${simulator()}<div class="section-heading"><h2>用語の小さな辞典</h2><span class="text-link">タップして意味を確認</span></div><div class="glossary">${learning.glossary.map(g=>`<details><summary>${esc(g.term)}</summary><p>${esc(g.definition)}</p><p>${esc(g.example)}</p></details>`).join("")}</div>`;}
  function methodView() {
    const tr=data.trackRecord;
    return `${pageIntro("OPEN DATA / OPEN LOGIC","何を根拠に、どう計算しているか。","見やすさだけでなく、確かめられることを大切に。情報の取得状態、見通しの仕組み、できないことを公開しています。")}${statusStrip()}<div class="legend-three"><div><strong><span class="badge blue">観測</span> いま確認できた情報</strong><p>価格・利回り・ニュースの見出し。時刻と出典を併記し、取得できなければ欠測として扱います。</p></div><div><strong><span class="badge green">市場の予想</span> Polymarketの価格</strong><p>そのイベントに対する参加者の見込み。正解を保証する客観確率でも、株価の上昇確率でもありません。</p></div><div><strong><span class="badge">推論</span> 条件付きの見通し</strong><p>過去の価格の勢いと一般的な経済関係に基づく解説。何が起きれば変わるかも示します。</p></div></div><section class="method-card"><h2>情報源と今回の取得結果</h2><div class="source-list">${data.sources.map(s=>`<div class="source-line"><div>${link(s.url,s.name)}<small style="display:block">取得 ${s.count??0}件${Number.isFinite(s.displayedCount)?` / 掲載 ${s.displayedCount}件`:""} · ${s.total?`${s.total}銘柄中 · `:""}${date(s.attemptedAt,true)} JST</small></div><small>${s.status==="ok"?"正常取得":s.status==="partial"?"一部取得失敗":"取得失敗・前回値がある場合のみ表示"}</small><span class="badge ${s.status==="ok"?"green":"amber"}">${s.status==="ok"?"取得済み":s.status==="partial"?"一部失敗":"失敗"}</span></div>`).join("")}</div><p style="margin-top:18px">Yahoo Financeの公開チャート、PolymarketのGamma API、NHK・BBC・中央銀行の公開RSSを利用。日本経済新聞の見出しはGoogleニュース経由で取得し、配信元の媒体名とドメインを照合しています。非公式の価格エンドポイントは仕様変更・制限の可能性があります。記事本文の複製、X投稿の自動収集、取引操作は行いません。</p></section>${scoreGuide()}<section class="method-card"><h2>見通しと、数字の意味</h2><p>${esc(data.method.newsUse)}</p><code>${esc(data.method.formula)}</code><p>このスコアは過去の変動に対する勢いの尺度で、−100〜100です。上昇確率への変換はしていません。±18以上を方向ありとする閾値は、解説用に設定したルールで、利益を最大化するよう検証された値ではありません。</p><p style="margin-top:12px">${esc(data.method.range)}</p><p style="margin-top:12px">価格の前日比は、取引所時間帯で直前の取引日終値と比較します。暗号資産もこの日次基準で、常に直近24時間のリターンを表すわけではありません。利回りはbpで差分を表示し、1bp = 0.01パーセントポイントです。</p></section><section class="method-card"><h2>観測後の検証を、積み重ねる。</h2><p>公開後に保存した観測値で、勢いの方向がその後の値動きと一致したかを確認します。初回から都合のよい的中率を表示することはありません。</p><div class="history-stats">${tr.stats.map(s=>`<div><span>${s.days}日後の方向一致</span><strong>${s.n?fmt(s.hitRate,1)+"%":"蓄積中"}</strong><span>${s.n}件${s.n?` / ${s.correct}件一致`:" · 未検証"}</span></div>`).join("")}</div><p>${esc(tr.note)}</p><p class="micro">収集開始 ${date(tr.since,true)} JST · ${tr.snapshotCount}スナップショット。45日分を保持。方向なし（±18未満）を除外するため、全ケースの成績ではありません。サンプルが少ない間の比率は不安定です。</p></section><section class="method-card"><h2>更新スケジュールと取得失敗</h2><p>GitHub Actionsの設定は毎時17分（JSTでも毎時17分）。ページは5分おきに公開済みデータの更新を確認します。GitHub側の混雑で実行が遅れたり、実行されない場合があります。取得処理から2時間30分を超えると、画面に遅延を表示します。</p><p style="margin-top:12px">取得に失敗した銘柄は、元の観測時刻を保った前回データを表示。新たな方向スコアの材料には使いません。96時間を超えた価格（暗号資産は30時間）では振れ幅を表示しません。これは休場判定ではなく鮮度の上限です。</p><p style="margin-top:12px">公開リポジトリの定期実行は、GitHubの仕様により60日間活動がないと停止する場合があります。更新ログをデータ用ブランチに保存し、Actionsの実行状態も確認できます。</p><p class="micro">${link("https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule","GitHubの定期実行の公式仕様")}</p></section><section class="method-card"><h2>このサイトの限界</h2><ul>${data.method.limits.map(s=>`<li>${esc(s)}</li>`).join("")}</ul><p>特定の先生の監修・公式サービスではありません。身近なたとえと論理の順番を使い、独自の文章で説明しています。</p></section>`;
  }
  function empty(text) {return `<div class="empty">${esc(text)}</div>`;}
  function render() {
    if(!data||!learning)return;
    $("#viewName").textContent=viewNames[state.view];
    document.querySelectorAll("[data-view]").forEach(a=>{const active=a.dataset.view===state.view;a.classList.toggle("active",active);if(active)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current");});
    $("#app").innerHTML=({overview,outlook:outlookView,prediction:predictionView,news:newsView,learn:learnView,method:methodView}[state.view])();
    updateSim();
  }
  function navigate() {let view=location.hash.slice(1).split("?")[0];state.view=viewNames[view]?view:"overview";state.search="";state.topic="all";state.newsSource="all";state.newsHours=0;$("#sidebar").classList.remove("open");$("#menuButton").setAttribute("aria-expanded","false");render();window.scrollTo({top:0,behavior:"instant"});}
  function openDialog(html) {$("#dialogContent").innerHTML=html;if(!$("#detailDialog").open)$("#detailDialog").showModal();}
  function openLesson(id) {
    const t=learning.topics.find(t=>t.id===id);if(!t)return;state.lesson=id;
    openDialog(`<header class="dialog-header"><div class="eyebrow">${esc(t.eyebrow)}</div><h2 id="dialogTitle">${esc(t.title)}</h2><p>${esc(t.summary)}</p></header><div class="lesson-body"><div class="analogy"><b>まずは、身近なたとえから。</b><p>${esc(t.analogy)}</p></div><h3>一歩ずつ、つながりを追う。</h3><ol>${t.steps.map(s=>`<li>${esc(s)}</li>`).join("")}</ol><div class="counter"><strong>反対のことが起きるのは？</strong>${esc(t.exception)}</div><h3>ニュースで確認するポイント</h3><ul>${t.watch.map(s=>`<li>${esc(s)}</li>`).join("")}</ul><div class="quiz"><h3>理解を確かめる、ひと問い。</h3><p>${esc(t.quiz.question)}</p>${t.quiz.choices.map((c,i)=>`<button data-answer="${i}">${i+1}. ${esc(c)}</button>`).join("")}<div class="quiz-result" id="quizResult" role="status"></div></div><p class="micro" style="margin-top:20px">参考：${(learning.sources||[]).filter(s=>(t.sourceIds||[]).includes(s.id)).map(s=>link(s.url,s.title||s.name||s.label)).join(" / ")}</p></div>`);
  }
  function toast(message) {$("#toast").textContent=message;$("#toast").classList.add("show");setTimeout(()=>$("#toast").classList.remove("show"),3500);}
  async function refresh(manual=false) {
    if(refreshing)return;refreshing=true;
    try {
      if(location.protocol==="file:"){if(manual)toast("これは保存版です。公開サイトで最新データを確認してください。");return;}
      const res=await fetch(`./data/snapshot.json?t=${Math.floor(Date.now()/300000)}`,{cache:"no-store"});if(!res.ok)throw Error("HTTP "+res.status);
      const next=await res.json();if(next.schemaVersion!==1||!Array.isArray(next.assets))throw Error("データ形式が不正です");
      const changed=next.generatedAt!==data?.generatedAt;
      data=next;if(changed)render();
      if(manual)toast(changed?"新しい公開データを反映しました。":"公開データは現在の表示と同じです。取得は毎時17分に予定されています。");
    } catch(e) {if(manual)toast("最新データを取得できませんでした。保存済みの時刻を確認してください。");}finally{refreshing=false;}
  }
  document.addEventListener("click",e=>{
    const b=e.target.closest("button");if(!b)return;
    if(b.dataset.days||b.dataset.sigma){if(b.dataset.days)state.days=+b.dataset.days;if(b.dataset.sigma)state.sigma=+b.dataset.sigma;if(b.closest("#detailDialog")){const q=asset(state.asset);$("#dialogContent").innerHTML=`<header class="dialog-header"><h2 id="dialogTitle">${esc(q.name)}</h2></header><div style="margin-top:20px">${chartPanel(q)}</div>`;}else render();}
    if(b.dataset.newsHours!==undefined){state.newsHours=+b.dataset.newsHours;render();}
    if(b.dataset.asset){state.asset=b.dataset.asset;render();}
    if(b.dataset.group){state.group=b.dataset.group;const scroll=window.scrollY;render();window.scrollTo(0,scroll);}
    if(b.dataset.topic){state.topic=b.dataset.topic;render();}
    if(b.dataset.lesson)openLesson(b.dataset.lesson);
    if(b.dataset.outlook){const o=data.outlooks.find(o=>o.id===b.dataset.outlook);openDialog(`<header class="dialog-header"><div class="eyebrow">EVIDENCE & SCENARIOS</div><h2 id="dialogTitle">${esc(o.title)}の見通し</h2></header>${outlookFull(o)}`);}
    if(b.dataset.detailAsset){state.asset=b.dataset.detailAsset;const q=asset(state.asset);openDialog(`<header class="dialog-header"><h2 id="dialogTitle">${esc(q.name)}</h2><p>観測値と、過去の変動から計算した幅</p></header><div style="margin-top:20px">${chartPanel(q)}</div>`);}
    if(b.dataset.answer!==undefined){const t=learning.topics.find(t=>t.id===state.lesson),chosen=+b.dataset.answer;document.querySelectorAll("[data-answer]").forEach(el=>{el.disabled=true;el.classList.toggle("correct",+el.dataset.answer===t.quiz.answerIndex);el.classList.toggle("wrong",el===b&&chosen!==t.quiz.answerIndex);});$("#quizResult").textContent=(chosen===t.quiz.answerIndex?"正解です。":"ここが考えどころです。")+t.quiz.explanation;}
  });
  document.addEventListener("input",e=>{
    if(e.target.id==="searchInput"){state.search=e.target.value;if(state.view==="news")$("#newsResults").innerHTML=filteredNews().map(newsCard).join("")||empty("該当するニュースはありません。");else if(state.view==="prediction")$("#pmResults").innerHTML=filteredPM().map(pmCard).join("")||empty("該当する市場はありません。");}
    if(["rateSlider","oilSlider"].includes(e.target.id))updateSim();
  });
  document.addEventListener("change",e=>{if(e.target.id==="newsSource"){state.newsSource=e.target.value;$("#newsResults").innerHTML=filteredNews().map(newsCard).join("")||empty("この条件のニュースはありません。");}if(e.target.id==="weekOnly"){state.weekOnly=e.target.checked;render();}});
  $("#dialogClose").addEventListener("click",()=>$("#detailDialog").close());
  $("#detailDialog").addEventListener("click",e=>{if(e.target===$("#detailDialog")){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
  $("#menuButton").addEventListener("click",()=>{const open=$("#sidebar").classList.toggle("open");$("#menuButton").setAttribute("aria-expanded",String(open));});
  $("#refreshButton").addEventListener("click",()=>refresh(true));
  window.addEventListener("hashchange",navigate);
  function clock(){ $("#topClock").textContent=date(new Date().toISOString(),true); }
  async function start(){
    try{if(!data||!learning){const results=await Promise.all([fetch("./data/snapshot.json"),fetch("./data/learn.json")]);[data,learning]=await Promise.all(results.map(r=>{if(!r.ok)throw Error("data unavailable");return r.json();}));}navigate();clock();setInterval(clock,60000);setInterval(()=>refresh(false),300000);}
    catch(e){$("#app").innerHTML=empty("初期データを読み込めませんでした。通信状態とPagesの公開状況を確認してください。");}
  }
  start();
})();
