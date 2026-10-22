"""Select up to three current, distinct market themes from attributed headlines.

This is a deterministic reading guide, not article-body analysis or causal
attribution. All transmission mechanisms remain conditional, including when a
headline contains a denial, a forecast, or an unconfirmed report.
"""
from __future__ import annotations

import datetime as dt
import math
import re
import unicodedata
from urllib.parse import urlparse


LOOKBACK_HOURS = 48
SELECTION_NOTE = "直近48時間の取得済み見出しから、市場への関連性・新しさ・関連価格の変動を基準に最大3件を選択。同じテーマは1枠。世界全体の重要度ランキングではありません。"
EVIDENCE_NOTE = "報道は見出しのみ確認。影響の説明はinsightの条件付き推論です。ニュースが値動きの原因だと確定したものではなく、勢いスコアへの加算もしていません。"


def has(pattern, title):
    return bool(re.search(pattern, title, re.I))


def timestamp(value):
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(dt.timezone.utc) if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def fresh_quote(q, now):
    at = timestamp(q.get("observedAt"))
    return (q.get("status") == "ok" and not q.get("stale") and finite(q.get("price"))
            and at is not None and -300 <= (now - at).total_seconds()
            <= (30 if q.get("group") == "crypto" else 96) * 3600)


def profile(title):
    """Require a market subject AND a catalyst; generic topic labels are insufficient."""
    def item(key, label, weight, ids, outlooks, summary, chain, watch, kind="catalyst"):
        return dict(theme=key, label=label, weight=weight, assetIds=ids, outlookIds=outlooks,
                    summary=summary, chain=chain, watch=watch, kind=kind)

    if has(r"関税|輸出規制|輸出制限|貿易摩擦|\btariffs?\b|export (?:curbs|controls|ban)", title):
        return item("trade", "貿易・規制", 84, ["nikkei", "sp500"], ["stocks", "tech"],
                    "関税や輸出規制が強まれば、仕入れ費用と売上に響き、企業利益の重荷になります。",
                    ["貿易条件", "費用・売上", "企業利益"],
                    "実施日と対象品目を確認。適用除外や延期なら負担が軽くなり、拡大なら逆風です。")

    middle_east = has(r"イラン|イスラエル|サウジ|ホルムズ|中東|\biran\b|\bisrael\b|hormuz|middle east|saudi", title)
    conflict = has(r"攻撃|停戦|封鎖|軍事|戦争|退避|協議|衝突|\bwar\b|attack|ceasefire|blockade|strike", title)
    oil = has(r"原油|石油|OPEC|\boil\b|crude|\bbrent\b|\bWTI\b|ガス田", title)
    supply = has(r"供給|減産|増産|在庫|輸送|採掘|輸出|急騰|急落|supply|output|production|inventory|inventories|surge|plunge", title)
    if (middle_east and conflict) or (oil and supply):
        return item("energy", "原油・中東情勢", 84, ["oil", "brent"], ["energy", "stocks"],
                    "供給が滞れば原油高に。燃料代の増加は企業の利益を圧迫し、物価も押し上げます。",
                    ["供給・輸送", "原油と燃料代", "物価・企業利益"],
                    "実際に供給や輸送が止まるかを確認。停戦の実行・供給回復なら、原油高の圧力は和らぎます。")

    policy = has(r"利上げ|利下げ|金利|金融政策|政策決定|interest rates?|monetary policy|rate (?:cut|hike|decision)", title)
    boj = has(r"日銀|日本銀行|bank of japan|\bBOJ\b", title)
    central = has(r"FRB|\bFed\b|FOMC|ECB|中銀|中央銀行|central bank|bank of england", title)
    if policy and (boj or central):
        if boj:
            return item("rates", "日銀・円の行方", 83, ["usdjpy", "nikkei"], ["fx", "stocks"],
                        "日米の金利差が縮むなら円高材料。円高は輸入費用を抑える一方、輸出企業には逆風にもなります。",
                        ["日銀の政策見通し", "日米の金利差", "円・日本株"],
                        "観測報道と日銀の正式決定を照合。金利差が広がる結果なら、円安方向の材料になります。")
        european = has(r"ECB|欧州|ユーロ|european|euro area", title)
        british = has(r"英中銀|イギリス|英国|bank of england", title)
        ids = ["europe", "eurusd"] if european else ["ftse"] if british else ["us10y", "nasdaq"]
        return item("rates", "中央銀行・金利", 82, ids, ["rates", "stocks"],
                    "予想以上の利上げなら借入費用が増え、株価には重荷。利下げでも景気悪化が理由なら要注意です。",
                    ["政策の見通し", "お金を借りる費用", "債券・株・為替"],
                    "正式発表と事前の見方の差を確認。予想通りなら、追加の値動きが小さい場合もあります。")

    ai = has(r"(?<![a-z])AI(?![a-z])|半導体|メタ|エヌビディア|テスラ|マイクロソフト|アルファベット|TSMC|\bmeta\b|nvidia|tesla|microsoft|alphabet|openai|semiconductor", title)
    business = has(r"決算|利益|増益|減益|赤字|黒字|投資|受注|売上|見通し|財務|制裁金|買収|統合|earnings|profit|revenue|investment|spending|fined|merger", title)
    if ai and business:
        ids = []
        for pattern, key in [(r"日経平均|日本株|東証", "nikkei"), (r"メタ|\bmeta\b", "meta"),
                             (r"テスラ|tesla", "tesla"), (r"エヌビディア|nvidia", "nvidia"),
                             (r"マイクロソフト|microsoft", "microsoft"), (r"TSMC|台湾積体", "tsmc")]:
            if has(pattern, title):
                ids.append(key)
        ids = list(dict.fromkeys(ids + ["nasdaq", "nvidia"]))[:2]
        return item("tech", "AI・企業の利益", 81, ids, ["tech", "stocks"],
                    "AIの売上が伸びても、投資や費用が利益を圧迫すれば逆風。株価は『期待との差』で動きます。",
                    ["売上と投資負担", "将来の利益予想", "AI・関連株"],
                    "次の決算・会社見通しで利益率と手元に残るお金を確認。期待を超える改善なら支え、悪化なら重荷です。")

    macro = has(r"消費者物価|インフレ|\bCPI\b|\bPCE\b|inflation|\bGDP\b|雇用統計|失業率|payrolls|unemployment|賃上げ|春闘", title)
    macro_event = has(r"統計|発表|上昇|低下|加速|鈍化|上回|下回|最高|最低|要求|\d\s*[%％]|figures|data|rise|fall|highest|lowest|accelerat|slow|report", title)
    if macro and macro_event:
        if has(r"春闘|賃上げ", title):
            return item("rates", "賃金・日銀の見通し", 79, ["usdjpy", "nikkei"], ["fx", "stocks"],
                        "賃上げが実現して消費や物価を押し上げれば、日銀の政策と円相場を考える材料になります。",
                        ["賃上げの見込み", "消費と物価", "日銀・円相場"],
                        "要求と実際の賃上げを区別。物価への波及や日銀の発言が強ければ円高材料、弱ければ見方を修正します。")
        japan = has(r"日本|全国|東京都|春闘|賃上げ|\bjapan\b", title)
        britain = has(r"英国|イギリス|\bUK\b|britain|chancellor", title)
        return item("rates", "物価・景気の転機", 79,
                    ["usdjpy", "nikkei"] if japan else ["ftse"] if britain else ["us10y", "sp500"],
                    ["rates", "stocks"], "物価の上振れは利上げ材料。景気の弱さは利下げ材料ですが、企業の売上にも響きます。",
                    ["物価・景気の情報", "金利と利益の予想", "債券・株・為替"],
                    "実績が事前予想を上回ったかを確認。物価と景気のどちらが動いたかで、株への影響は変わります。")

    if has(r"国債|treasury|government bond", title) and has(r"利回り|入札|財政|債務|yield|auction|debt|borrowing", title):
        ids = ["europe", "eurusd"] if has(r"フランス|ドイツ|欧州|france|germany", title) else ["usdjpy", "nikkei"] if has(r"日本|円債|\bjapan\b", title) else ["us10y", "nasdaq"]
        return item("rates", "国債・資金調達", 77, ids, ["rates", "stocks"],
                    "国債利回りが上がると借入費用も上がりやすく、株の評価には重荷。景気への期待で上がる場合もあります。",
                    ["国債の需給・財政", "利回り", "借入費用・株の評価"],
                    "入札結果と利回りの継続性を確認。需給が落ち着けば負担は和らぎます。当該国債を未収集の場合は関連市場を表示します。")

    if has(r"ビットコイン|暗号資産|仮想通貨|イーサリアム|bitcoin|ethereum|crypto", title) and has(r"ETF|流入|流出|規制|価格|急|上昇|下落|投資|資金|fund|inflow|outflow|regulat|price|rally|fall|surge|plunge", title):
        return item("crypto", "暗号資産・資金の流れ", 77, ["bitcoin", "ethereum"], ["crypto"],
                    "買い資金が増えれば価格を支え、資金流出や借金を使った取引の解消が重なると下落が増幅します。",
                    ["資金流入・規制", "買い手と売り手", "暗号資産の価格"],
                    "資金の出入りと規制の正式発表を確認。流入が続くか、反転するかが分岐点です。")

    if has(r"日経平均|日本株|米国株|米株|NASDAQ|S&P.?500|ダウ平均|株式市場|stock markets?|wall street", title) and has(r"急落|急騰|反落|反発|下落|上昇|売り|買い|高値|安値|rally|fall|surge|plunge|sell.off", title):
        ids = ["nikkei", "usdjpy"] if has(r"日経|日本|東証", title) else ["sp500", "nasdaq"]
        return item("stocks", "株式市場の変調", 57, ids, ["stocks"],
                    "これは値動きを伝える報道です。下落・上昇という結果だけでは、何が原因だったかまでは決まりません。",
                    ["株価の変化を確認", "金利・利益・政策を照合", "持続するかを点検"],
                    "次の市場でも動きが広がるかを確認。金利・企業見通しなどの変化が続かなければ、反転する場合もあります。", "market-observation")
    return None


def normalize(title):
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFKC", title).lower())


def similar(a, b):
    a, b = normalize(a), normalize(b)
    if a == b:
        return True
    aa, bb = {a[i:i + 3] for i in range(len(a) - 2)}, {b[i:i + 3] for i in range(len(b) - 2)}
    return bool(aa and bb) and len(aa & bb) / len(aa | bb) >= .6


def create_briefing(news, assets, now):
    byid = {q["id"]: q for q in assets}
    candidates = []
    for n in news:
        pub = timestamp(n.get("publishedAt"))
        try:
            u = urlparse(n.get("url", ""))
            valid_url = u.scheme == "https" and u.hostname and not u.username
        except ValueError:
            valid_url = False
        if (n.get("status") != "ok" or not pub or not valid_url or not n.get("source")
                or not 0 <= (now - pub).total_seconds() <= LOOKBACK_HOURS * 3600):
            continue
        p = profile(n.get("title", ""))
        if not p:
            continue
        age = (now - pub).total_seconds() / 3600
        qs = [byid[key] for key in p["assetIds"] if key in byid and fresh_quote(byid[key], now)]
        moves = []
        for q in qs:
            change = q.get("changeBps") if q.get("unit") == "yield" else q.get("changePct")
            if finite(change) and finite(q.get("sigma")) and q["sigma"] > 0:
                moves.append(abs(change) / q["sigma"])
        reasons = ["市場に関連する見出し", "24時間以内" if age <= 24 else "48時間以内"]
        market_word = has(r"株|相場|日経平均|NASDAQ|S&P.?500|金利|原油|stocks?|markets?|yields?", n["title"])
        causal_word = has(r"招いた|背景|嫌気|好感|下押し|押し上げ|受け|driven by|on fears|amid", n["title"])
        connection = 16 if market_word and causal_word else 0
        if connection:
            reasons.append("見出しに市場とのつながりへの言及")
        if moves:
            reasons.append("関連価格の変動を照合")
        weight = p.pop("weight") + max(0, 24 - age / 2) + min(12, max(moves, default=0) * 4) + connection
        if n.get("tier") == "一次資料":
            weight += 4
        candidates.append({**p, "id": n["id"], "newsId": n["id"], "publishedAt": n["publishedAt"],
                           "selectedBecause": reasons, "selectionScore": round(weight, 2)})
    candidates.sort(key=lambda s: (s["selectionScore"], s["publishedAt"], s["id"]), reverse=True)
    selected, themes, titles = [], set(), []
    headlines = {n["id"]: n["title"] for n in news}
    for c in candidates:
        title = headlines[c["newsId"]]
        if c["theme"] in themes or any(similar(title, old) for old in titles):
            continue
        selected.append(c)
        themes.add(c["theme"])
        titles.append(title)
        if len(selected) == 3:
            break
    return {"version": 1, "generatedAt": now.isoformat().replace("+00:00", "Z"),
            "status": "ok" if len(selected) == 3 else "limited", "lookbackHours": LOOKBACK_HOURS,
            "candidateCount": len(candidates), "selectionNote": SELECTION_NOTE,
            "evidenceNote": EVIDENCE_NOTE, "stories": selected}
