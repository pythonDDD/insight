#!/usr/bin/env python3
"""Hourly public-data snapshot. Python 3.12+, standard library only.

No LLM, trading, secrets, or invented market data. Explanations are deterministic
and conditional. A failed source retains its original timestamp, never a new one.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import email.utils
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from config import ASSETS, FEEDS, TOPICS

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site" / "data"
UTC = dt.timezone.utc
JST = ZoneInfo("Asia/Tokyo")
NOW = dt.datetime.now(UTC)
WINDOW_START = dt.datetime.combine(NOW.astimezone(JST).date() + dt.timedelta(days=1), dt.time.min, JST).astimezone(UTC)
WINDOW_END = dt.datetime.combine(NOW.astimezone(JST).date() + dt.timedelta(days=7), dt.time.max, JST).astimezone(UTC)
USER_AGENT = "insight-market-observatory/1.0 (public educational data reader)"


def iso(value=None):
    return (value or NOW).astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_time(value):
    if not value:
        return None
    try:
        t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        try:
            t = email.utils.parsedate_to_datetime(str(value))
        except (ValueError, TypeError, IndexError):
            return None
    return t.replace(tzinfo=UTC) if not t.tzinfo else t.astimezone(UTC)


def num(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def safe_url(url):
    try:
        u = urllib.parse.urlparse(url or "")
        return url if u.scheme == "https" and u.netloc and not u.username else ""
    except ValueError:
        return ""


def fetch(url, kind="json"):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/xml, text/xml, */*"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=22) as response:
                raw = response.read(12_000_000)
            return json.loads(raw) if kind == "json" else raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            # Do not evade rate limits or access restrictions.
            if exc.code in (401, 403, 429) or attempt:
                raise
        except (TimeoutError, OSError):
            if attempt:
                raise
        time.sleep(1)


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def get_quote(spec):
    key, name, region, symbol, group, currency, unit = spec
    query = urllib.parse.urlencode({"interval": "1d", "range": "3mo"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol, safe='')}?{query}"
    payload = fetch(url)
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result:
        raise ValueError("価格が返されませんでした")
    meta = result["meta"]
    values = result["indicators"]["quote"][0]["close"]
    history = [{"t": int(t), "v": float(v)} for t, v in zip(result["timestamp"], values)
               if num(v) is not None and v > 0 and t <= NOW.timestamp() + 300]
    price = num(meta.get("regularMarketPrice"))
    stamp = num(meta.get("regularMarketTime"))
    if price is None or price <= 0 or not stamp or stamp > NOW.timestamp() + 300:
        raise ValueError("価格・観測時刻が不正です")
    observed = dt.datetime.fromtimestamp(stamp, UTC)
    # previousClose from a ranged chart may be the range-start close, NOT yesterday.
    # Locate the previous trading date in the exchange's own timezone instead.
    tz = ZoneInfo(meta.get("exchangeTimezoneName") or "UTC")
    quote_day = observed.astimezone(tz).date()
    completed = [h for h in history if dt.datetime.fromtimestamp(h["t"], UTC).astimezone(tz).date() < quote_day]
    previous = num(meta.get("previousClose")) or (completed[-1]["v"] if completed else None)
    change = (price / previous - 1) * 100 if previous else None
    daily = [h["v"] for h in completed[-61:]]
    if unit == "yield":
        movements = [(b - a) * 100 for a, b in zip(daily, daily[1:])]
        daily_move = (price - previous) * 100 if previous else None
        five_move = (price - daily[-5]) * 100 if len(daily) >= 5 else None
    else:
        movements = [math.log(b / a) * 100 for a, b in zip(daily, daily[1:])]
        daily_move = change
        five_move = (price / daily[-5] - 1) * 100 if len(daily) >= 5 else None
    sigma = statistics.stdev(movements) if len(movements) >= 15 else None
    # Bounded descriptive momentum, NOT an estimated probability of a future rise.
    score = None
    if sigma and daily_move is not None and five_move is not None:
        score = max(-100, min(100, round(35 * (0.65 * five_move / (sigma * math.sqrt(5)) + 0.35 * daily_move / sigma))))
    return {"id": key, "name": name, "region": region, "symbol": symbol, "group": group,
            "currency": currency, "unit": unit, "price": price, "previous": previous,
            "changePct": change, "changeBps": daily_move if unit == "yield" else None,
            "fiveMove": five_move, "sigma": sigma, "sampleSize": len(movements), "score": score,
            "observedAt": iso(observed), "fetchedAt": iso(), "status": "ok", "history": history[-65:],
            "source": "Yahoo Finance", "sourceUrl": f"https://finance.yahoo.com/quote/{urllib.parse.quote(symbol, safe='')}/",
            "apiUrl": url, "exchange": meta.get("fullExchangeName", ""),
            "delayNote": "配信遅延の可能性あり。価格は表示時刻の観測値。", "exchangeTimezone": str(tz)}


def collect_quotes(old):
    prior = {q["id"]: q for q in old.get("assets", [])}
    results, errors = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        jobs = {pool.submit(get_quote, spec): spec for spec in ASSETS}
        for job in concurrent.futures.as_completed(jobs):
            spec = jobs[job]
            try:
                results[spec[0]] = job.result()
            except Exception as exc:
                errors.append(f"{spec[1]}: {type(exc).__name__} {str(exc)[:80]}")
                if spec[0] in prior:
                    results[spec[0]] = {**prior[spec[0]], "status": "cached", "error": "今回の取得に失敗。前回の観測値です。"}
                else:
                    results[spec[0]] = {"id": spec[0], "name": spec[1], "region": spec[2], "symbol": spec[3], "group": spec[4], "currency": spec[5], "unit": spec[6], "status": "unavailable", "price": None, "score": None, "history": []}
    for q in results.values():
        stamp = parse_time(q.get("observedAt"))
        hours = (NOW - stamp).total_seconds() / 3600 if stamp else None
        q["ageHours"] = round(hours, 1) if hours is not None else None
        q["stale"] = hours is None or hours > (30 if q["group"] == "crypto" else 96)
    return [results[a[0]] for a in ASSETS], {"id": "yahoo", "name": "Yahoo Finance", "url": "https://finance.yahoo.com/", "status": "ok" if not errors else "partial" if len(errors) < len(ASSETS) else "error", "count": sum(q.get("status") == "ok" for q in results.values()), "total": len(ASSETS), "errors": errors, "attemptedAt": iso()}


def classify(text, default="economy"):
    return next((key for key, t in TOPICS.items() if re.search(t["pattern"], text, re.I)), default)


def array_field(value):
    try:
        return json.loads(value) if isinstance(value, str) else value or []
    except (ValueError, TypeError):
        return []


def normalize_market(m, previous):
    question = str(m.get("question", ""))
    end = parse_time(m.get("endDate"))
    if not end or end < WINDOW_START or end > NOW + dt.timedelta(days=60) or m.get("closed") or not m.get("active", True) or m.get("acceptingOrders") is False:
        return None
    # Explicit topic allowlist; sports, entertainment and 5-minute betting are not useful here.
    if not re.search(r"bitcoin|ethereum|\bbtc\b|\beth\b|\bfed\b|interest rate|inflation|recession|s&p|nasdaq|\boil\b|\bgold\b|treasury|nvidia|microsoft|tesla|meta|apple|alphabet|openai|iran|israel|russia|ukraine|ceasefire|tariff|china|taiwan|hormuz|government shutdown|election|congress|senate|presiden", question, re.I):
        return None
    if re.search(r"\bvs\.?\b|\bwin on\b|up or down.*\d{1,2}:\d{2}|\b(?:5|15) minute", question, re.I):
        return None
    outcomes = array_field(m.get("outcomes"))
    prices = [num(p) for p in array_field(m.get("outcomePrices"))]
    if len(outcomes) != len(prices) or not prices or any(p is None or not 0 <= p <= 1 for p in prices):
        return None
    liq = num(m.get("liquidityNum") or m.get("liquidity")) or 0
    volume = num(m.get("volume24hr")) or 0
    if liq < 1000 or volume < 100:
        return None
    yes_index = next((i for i, o in enumerate(outcomes) if o.lower() == "yes"), None)
    key = str(m["id"])
    probability = prices[yes_index] if yes_index is not None else None
    prev = previous.get(key)
    prior_prob = prev.get("probability") if prev else None
    change = 100 * (probability - prior_prob) if probability is not None and prior_prob is not None and prev.get("fetchedAt") != iso() else None
    spread = num(m.get("spread"))
    topic = classify(question)
    return {"id": key, "question": question, "topic": topic, "category": TOPICS[topic]["name"],
            "outcomes": [{"label": str(label), "probability": p} for label, p in zip(outcomes, prices)],
            "probability": probability, "changePp": round(change, 2) if change is not None else None,
            "comparisonAt": prev.get("fetchedAt") if change is not None else None,
            "endAt": iso(end), "withinWeek": end <= WINDOW_END,
            "fetchedAt": iso(), "updatedAt": m.get("updatedAt"), "volume24h": volume,
            "liquidity": liq, "spread": spread, "lowLiquidity": liq < 10000 or (spread is not None and spread > .05),
            "url": "https://polymarket.com/event/" + str((m.get("events") or [{}])[0].get("slug") or m.get("slug", "")),
            "resolutionSource": safe_url(m.get("resolutionSource", "")),
            "conditionNote": "期限・判定条件は元の市場で確認。Yes価格の目安であり、統計モデルが計算した客観確率ではありません。",
            "status": "ok"}


def collect_polymarket(old):
    prior = {m["id"]: m for m in old.get("predictions", [])}
    raw, errors = {}, []
    base = "https://gamma-api.polymarket.com/markets"
    queries = [
        {"active": "true", "closed": "false", "limit": 200, "order": "volume24hr", "ascending": "false", "end_date_min": iso(WINDOW_START), "end_date_max": iso(WINDOW_END)},
        {"active": "true", "closed": "false", "limit": 200, "order": "volume24hr", "ascending": "false"},
    ]
    for query in queries:
        try:
            response = fetch(base + "?" + urllib.parse.urlencode(query))
            if not isinstance(response, list):
                raise ValueError("market list expected")
            raw.update({str(m["id"]): m for m in response})
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {str(exc)[:100]}")
    normalized = [normalize_market(m, prior) for m in raw.values()]
    valid = sorted([m for m in normalized if m], key=lambda m: (not m["withinWeek"], -m["volume24h"]))
    # Bound concentration: avoid filling the screen with one BTC threshold family.
    selected, topic_counts = [], {}
    for m in valid:
        count = topic_counts.get(m["topic"], 0)
        if count < 8 and len(selected) < 30:
            selected.append(m)
            topic_counts[m["topic"]] = count + 1
    if not raw:
        selected = [{**m, "status": "cached", "withinWeek": parse_time(m["endAt"]) <= WINDOW_END} for m in prior.values() if parse_time(m.get("endAt")) and parse_time(m["endAt"]) >= WINDOW_START]
    return selected, {"id": "polymarket", "name": "Polymarket Gamma API", "url": "https://polymarket.com/", "status": "ok" if not errors else "partial" if raw else "error", "count": len(selected), "scanned": len(raw), "errors": errors, "attemptedAt": iso(), "note": "出来高上位のサンプル。全市場を網羅するものではありません。"}


def text_of(node, name):
    child = next((c for c in node if c.tag.split("}")[-1] == name), None)
    return "".join(child.itertext()).strip() if child is not None else ""


def parse_feed(xml, feed):
    root = ET.fromstring(xml)
    output = []
    for item in root.iter():
        if item.tag.split("}")[-1] not in ("item", "entry"):
            continue
        title = re.sub(r"\s+", " ", text_of(item, "title"))[:240]
        link = text_of(item, "link")
        if not link:
            link = next((n.get("href", "") for n in item if n.tag.split("}")[-1] == "link"), "")
        pub = parse_time(text_of(item, "pubDate") or text_of(item, "date") or text_of(item, "published") or text_of(item, "updated"))
        if not title or not safe_url(link) or not pub or pub > NOW + dt.timedelta(minutes=5) or pub < NOW - dt.timedelta(days=7):
            continue
        topic = classify(title, feed["topic"] if feed["topic"] in TOPICS else "economy")
        output.append({"id": hashlib.sha256(link.encode()).hexdigest()[:14], "title": title, "url": link,
                       "source": feed["name"], "sourceId": feed["id"], "tier": feed["tier"],
                       "publishedAt": iso(pub), "fetchedAt": iso(), "topic": topic, "status": "ok"})
    return output[:30]


def collect_news(old):
    news, statuses = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(fetch, f["url"], "text"): f for f in FEEDS}
        for job in concurrent.futures.as_completed(jobs):
            f = jobs[job]
            try:
                items = parse_feed(job.result(), f)
                news.extend(items)
                statuses.append({**f, "status": "ok", "count": len(items), "attemptedAt": iso()})
            except Exception as exc:
                cached = [{**n, "status": "cached"} for n in old.get("news", []) if n.get("sourceId") == f["id"] and parse_time(n.get("publishedAt")) and parse_time(n["publishedAt"]) > NOW - dt.timedelta(days=7)]
                news.extend(cached)
                statuses.append({**f, "status": "error", "count": len(cached), "errors": [str(exc)[:100]], "attemptedAt": iso()})
    unique = {n["url"]: n for n in news}
    return sorted(unique.values(), key=lambda n: n["publishedAt"], reverse=True)[:100], sorted(statuses, key=lambda s: s["id"])


def parse_ics(text):
    """Parse the concrete BLS VEVENTs; never silently guess unknown timezones."""
    text = re.sub(r"\r?\n[ \t]", "", text)
    events = []
    for block in text.split("BEGIN:VEVENT")[1:]:
        props = {}
        start_key = None
        for line in block.split("END:VEVENT")[0].splitlines():
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            props[key] = val
            if key.startswith("DTSTART"):
                start_key = key
        if not start_key:
            continue
        val = props[start_key]
        try:
            if val.endswith("Z"):
                moment = dt.datetime.strptime(val, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
            elif "TZID=" in start_key:
                tz_name = start_key.split("TZID=")[1].strip('"')
                tz = ZoneInfo("America/New_York" if tz_name == "US-Eastern" else tz_name)
                moment = dt.datetime.strptime(val, "%Y%m%dT%H%M%S").replace(tzinfo=tz)
            else:
                continue  # An unspecified time must not be invented.
        except (ValueError, KeyError):
            continue
        if WINDOW_START <= moment <= WINDOW_END:
            title = props.get("SUMMARY", "BLS統計発表").replace("\\,", ",").replace("\\n", " ")
            events.append({"id": hashlib.sha256((title+val).encode()).hexdigest()[:12], "title": title,
                           "at": iso(moment), "sourceName": "米労働統計局（BLS）", "url": "https://www.bls.gov/schedule/",
                           "category": "economy", "importance": "経済指標", "explanation": "市場予想との差が、景気・物価・金利の見方を変えます。予想値はこのサイトでは取得していません。", "timeNote": "公式カレンダーの米東部時間をJSTへ換算", "verifiedAt": iso()})
    return events


def collect_events(old):
    curated = read_json(DATA / "events.json", [])
    future = [e for e in curated if parse_time(e.get("at")) and WINDOW_START <= parse_time(e["at"]) <= WINDOW_END]
    status = {"id": "bls", "name": "米労働統計局 カレンダー", "url": "https://www.bls.gov/schedule/", "attemptedAt": iso()}
    try:
        extra = parse_ics(fetch("https://www.bls.gov/schedule/news_release/bls.ics", "text"))
        future.extend(extra)
        status.update(status="ok", count=len(extra))
    except Exception as exc:
        cached = [e for e in old.get("events", []) if "BLS" in e.get("sourceName", "") and parse_time(e.get("at")) and WINDOW_START <= parse_time(e["at"]) <= WINDOW_END]
        future.extend(cached)
        status.update(status="error", count=len(cached), errors=[str(exc)[:100]])
    return sorted(future, key=lambda e: parse_time(e["at"])), status


def usable(q):
    return bool(q and q.get("price") is not None and not q.get("stale") and q.get("status") == "ok")


def create_outlooks(assets, news, markets):
    byid = {q["id"]: q for q in assets}
    definitions = [
        ("stocks", "世界の株式", ["sp500", "nasdaq", "nikkei", "europe", "ftse", "hangseng", "india"], "株価", "ai", "企業の利益見通しが改善し、長期金利が落ち着くなら上値を試しやすい。", "利益見通しの悪化や原油・金利の急上昇なら、反対方向に動きやすい。"),
        ("rates", "金利・国債", ["us10y", "us13w"], "利回り", "rates", "物価や国債供給への警戒が強まれば、利回りには上昇圧力。", "景気悪化や安全資産への資金移動なら、利回り低下・債券価格上昇も。"),
        ("crypto", "暗号資産", ["bitcoin", "ethereum"], "価格", "crypto", "資金流入が続き、金利・ドルの逆風が弱まれば、買い材料が増える。", "資金流出や規制の不意打ち、レバレッジ解消なら下落が拡大することも。"),
        ("gold", "金・貴金属", ["gold", "silver"], "価格", "rates", "実質金利が下がる、または安全資産需要が強まるなら支えになりやすい。", "実質金利やドルが上がると、金には下押し圧力。現金化の売りにも注意。"),
        ("energy", "原油・資源", ["oil", "brent", "copper"], "価格", "energy", "実際の供給減が需要減を上回るなら、資源価格は上がりやすい。", "供給の回復や景気減速で需要が落ちれば、原油は下がることもある。"),
        ("tech", "AI・テック企業", ["nvidia", "microsoft", "alphabet", "meta", "tesla", "tsmc"], "株価", "ai", "決算と先の利益見通しが事前の期待を上回れば、株価の支えになる。", "売上が増えても、投資負担・利益率・資金繰りが期待以下なら逆風。"),
        ("fx", "為替", ["usdjpy", "eurusd"], "通貨", "rates", "米金利が相対的に高まりドル需要が増えるなら、ドル高の材料。", "日銀・ECBの政策、リスク回避や介入で金利差と違う動きもある。"),
    ]
    out = []
    for key, title, ids, measure, topic, upside, downside in definitions:
        qs = [byid[i] for i in ids if usable(byid.get(i)) and byid[i].get("score") is not None]
        score = round(statistics.mean(q["score"] for q in qs)) if qs and key != "fx" else None
        label = "上向きの勢い" if score is not None and score >= 18 else "下向きの勢い" if score is not None and score <= -18 else "方向感が混在" if score is not None else "判断材料が不足" if key != "fx" else "通貨ペア別に確認"
        facts = []
        for q in qs[:3]:
            movement = f"{q['changeBps']:+.1f}bp" if q["unit"] == "yield" else f"{q['changePct']:+.2f}%"
            facts.append({"assetId": q["id"], "text": f"{q['name']}は直前の取引日終値比 {movement}。", "at": q["observedAt"], "url": q["sourceUrl"]})
        if key in ("stocks", "tech", "crypto", "gold") and usable(byid.get("us10y")):
            q = byid["us10y"]
            if q.get("changeBps") is not None:
                facts.append({"assetId": "us10y", "text": f"米10年債利回りの前日差は {q['changeBps']:+.1f}bp。将来利益の評価や資金移動に影響する材料。", "at": q["observedAt"], "url": q["sourceUrl"]})
        horizons = [
            {"days": 1, "label": "明日まで", "text": f"足元は「{label}」。新情報がなければ、この流れが続くかを確認。値動きだけでは明日の方向は確定できません。"},
            {"days": 3, "label": "3日先", "text": upside + " 発表前の期待と実際の差が分岐点です。"},
            {"days": 7, "label": "1週間先", "text": downside + " 時間が延びるほど新しい材料が入り、見通しは変わります。"},
        ]
        out.append({"id": key, "title": title, "assetIds": ids, "measure": measure, "topic": topic,
                    "score": score, "label": label, "coverage": f"{len(qs)}/{len(ids)}", "facts": facts,
                    "upside": upside, "downside": downside, "horizons": horizons,
                    "newsIds": [n["id"] for n in news if n["topic"] == topic][:3],
                    "marketIds": [m["id"] for m in markets if m["topic"] == topic][:3]})
    return out


def update_history(assets):
    history = read_json(DATA / "history.json", {"version": 1, "snapshots": []})
    cutoff = NOW - dt.timedelta(days=45)
    samples = [s for s in history.get("snapshots", []) if parse_time(s.get("at")) and parse_time(s["at"]) > cutoff]
    # One record per UTC hour; data is kept on the data branch by the workflow.
    hour = iso(NOW.replace(minute=0, second=0, microsecond=0))
    sample = {"at": iso(), "hour": hour, "assets": {q["id"]: {"price": q["price"], "score": q.get("score"), "observedAt": q["observedAt"], "unit": q["unit"]} for q in assets if usable(q)}}
    if sample["assets"]:
        samples = [s for s in samples if s.get("hour") != hour] + [sample]
    history["snapshots"] = samples[-1100:]
    write_json(DATA / "history.json", history)
    # Daily non-overlapping (per origin day) observations to avoid hourly pseudo-samples.
    stats = []
    for days in (1, 3, 7):
        correct = total = flat = 0
        seen = set()
        for s in samples:
            start = parse_time(s["at"])
            target = start + dt.timedelta(days=days)
            if target > NOW:
                continue
            end = next((e for e in samples if target <= parse_time(e["at"]) <= target + dt.timedelta(hours=4)), None)
            if not end:
                continue
            for key, a in s["assets"].items():
                unique = (start.astimezone(JST).date().isoformat(), key)
                score = a.get("score")
                b = end["assets"].get(key)
                if unique in seen or score is None or abs(score) < 18 or not b or b["observedAt"] == a["observedAt"]:
                    continue
                seen.add(unique)
                change = b["price"] - a["price"]
                if abs(change) < 1e-10:
                    flat += 1
                else:
                    total += 1
                    correct += (change > 0) == (score > 0)
        stats.append({"days": days, "n": total, "correct": correct, "flat": flat,
                      "hitRate": round(correct / total * 100, 1) if total else None})
    return {"since": samples[0]["at"] if samples else None, "snapshotCount": len(samples), "stats": stats,
            "note": "観測した勢いの方向と、その後の価格差を照合。各銘柄・各起点日1件、横ばい除外。データ間の相関・期間重複があり独立な試行ではありません。売買収益・取引費用は検証していません。"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="fail only if no fresh core data; cached data remains available")
    args = parser.parse_args()
    old = read_json(DATA / "snapshot.json", {})
    assets, quote_status = collect_quotes(old)
    print(f"prices: {quote_status['count']}/{len(ASSETS)}", flush=True)
    markets, pm_status = collect_polymarket(old)
    print(f"prediction markets: {len(markets)}", flush=True)
    news, feed_status = collect_news(old)
    events, event_status = collect_events(old)
    print(f"news: {len(news)}, events: {len(events)}", flush=True)
    track = update_history(assets)
    fresh = quote_status["count"] > 0 or any(m.get("status") == "ok" for m in markets)
    failures = sum(s["status"] != "ok" for s in [quote_status, pm_status, *feed_status, event_status])
    snapshot = {"schemaVersion": 1, "generatedAt": iso(), "lastSuccessfulAt": iso() if fresh else old.get("lastSuccessfulAt"),
                "status": "ok" if not failures else "partial" if fresh else "unavailable",
                "timezone": "Asia/Tokyo", "windowStart": iso(WINDOW_START), "windowEnd": iso(WINDOW_END),
                "assets": assets, "predictions": markets, "news": news, "events": events,
                "outlooks": create_outlooks(assets, news, markets), "trackRecord": track,
                "sources": [quote_status, pm_status, *feed_status, event_status],
                "topics": TOPICS, "method": {"version": "1.0", "kind": "transparent-rule-based", "scoreIsProbability": False,
                    "formula": "銘柄スコア = clip(35 × [0.65 × 5取引日変化 / (日次標準偏差 × √5) + 0.35 × 前日変化 / 日次標準偏差], −100, 100)。分類は±18。分類間の単純平均。為替は平均しない。",
                    "newsUse": "見出しをトピック分類して条件付きの因果説明につなぐ。記事本文の事実認定・感情判定・AIによる全文分析は行わない。Polymarketの価格は銘柄スコアに加算しない。",
                    "range": "直近最大60日次変化の標準偏差×√日数。価格は対数変化、利回りはbp変化。中心は最新価格でドリフトなし。確率付き予測区間ではなく過去の振れ幅の目安。休日は土日だけを除外、現地祝日は未調整。",
                    "limits": ["予測精度は未確立。過去の勢いが続く保証はありません。", "すべての国・情報・予測市場を網羅していません。", "ニュースの本文取得やXの投稿収集、経済指標コンセンサス取得は行っていません。", "先物は期近。限月交代により連続価格に段差が出る場合があります。", "金利は米国の市場利回りを表示。各国政策金利・実質金利のライブ値は取得していません。"]}}
    write_json(DATA / "snapshot.json", snapshot)
    print(json.dumps({"status": snapshot["status"], "generatedAt": snapshot["generatedAt"], "failedSources": failures}, ensure_ascii=False))
    if args.strict and not fresh:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
