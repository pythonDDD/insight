"""Public source definitions. No API keys, accounts, or trading endpoints."""
ASSETS = [
    ("sp500", "S&P 500", "米国・大型株", "^GSPC", "equity", "USD", "index"),
    ("nasdaq", "NASDAQ", "米国・ハイテク株", "^IXIC", "equity", "USD", "index"),
    ("dow", "ダウ平均", "米国・主要30社", "^DJI", "equity", "USD", "index"),
    ("nikkei", "日経平均", "日本", "^N225", "equity", "JPY", "index"),
    ("europe", "EURO STOXX 50", "ユーロ圏", "^STOXX50E", "equity", "EUR", "index"),
    ("ftse", "FTSE 100", "英国", "^FTSE", "equity", "GBP", "index"),
    ("hangseng", "ハンセン指数", "香港", "^HSI", "equity", "HKD", "index"),
    ("india", "SENSEX", "インド", "^BSESN", "equity", "INR", "index"),
    ("us10y", "米国10年債利回り", "長期金利・政策金利とは別", "^TNX", "rates", "PCT", "yield"),
    ("us13w", "米国13週国債利回り", "短期金利・割引率ベース", "^IRX", "rates", "PCT", "yield"),
    ("usdjpy", "ドル / 円", "上昇 = 円安", "JPY=X", "fx", "JPY", "fx"),
    ("eurusd", "ユーロ / ドル", "上昇 = ユーロ高", "EURUSD=X", "fx", "USD", "fx"),
    ("bitcoin", "Bitcoin", "ビットコイン", "BTC-USD", "crypto", "USD", "price"),
    ("ethereum", "Ethereum", "イーサリアム", "ETH-USD", "crypto", "USD", "price"),
    ("gold", "金先物", "COMEX・期近", "GC=F", "commodity", "USD", "futures"),
    ("silver", "銀先物", "COMEX・期近", "SI=F", "commodity", "USD", "futures"),
    ("oil", "WTI原油先物", "NYMEX・期近", "CL=F", "commodity", "USD", "futures"),
    ("brent", "ブレント原油先物", "ICE・期近", "BZ=F", "commodity", "USD", "futures"),
    ("copper", "銅先物", "COMEX・期近", "HG=F", "commodity", "USD", "futures"),
    ("nvidia", "NVIDIA", "AI・半導体", "NVDA", "tech", "USD", "price"),
    ("microsoft", "Microsoft", "AI・クラウド", "MSFT", "tech", "USD", "price"),
    ("alphabet", "Alphabet", "AI・検索", "GOOGL", "tech", "USD", "price"),
    ("meta", "Meta", "AI・広告", "META", "tech", "USD", "price"),
    ("tesla", "Tesla", "自動運転・EV", "TSLA", "tech", "USD", "price"),
    ("tsmc", "TSMC ADR", "半導体・台湾", "TSM", "tech", "USD", "price"),
]

FEEDS = [
    {"id": "nikkei_google", "name": "日本経済新聞（Googleニュース経由）", "url": "https://news.google.com/rss/search?q=site%3Anikkei.com%20when%3A7d&hl=ja&gl=JP&ceid=JP%3Aja", "tier": "報道", "topic": "economy", "publisher": "日本経済新聞", "publisherDomain": "nikkei.com", "via": "Googleニュース", "note": "配信メタデータの媒体名・ドメインを照合。見出しと記事へのリンクのみ。本文未取得・有料記事あり。"},
    {"id": "nhk_economy", "name": "NHK 経済", "url": "https://www.nhk.or.jp/rss/news/cat5.xml", "tier": "報道", "topic": "economy"},
    {"id": "nhk_world", "name": "NHK 国際", "url": "https://www.nhk.or.jp/rss/news/cat6.xml", "tier": "報道", "topic": "geopolitics"},
    {"id": "nhk_politics", "name": "NHK 政治", "url": "https://www.nhk.or.jp/rss/news/cat4.xml", "tier": "報道", "topic": "politics"},
    {"id": "bbc_business", "name": "BBC Business", "url": "https://feeds.bbci.co.uk/news/business/rss.xml", "tier": "報道", "topic": "economy"},
    {"id": "fed", "name": "米連邦準備制度（Fed）", "url": "https://www.federalreserve.gov/feeds/press_monetary.xml", "tier": "一次資料", "topic": "rates"},
    {"id": "ecb", "name": "欧州中央銀行（ECB）", "url": "https://www.ecb.europa.eu/rss/press.html", "tier": "一次資料", "topic": "rates"},
    {"id": "boj", "name": "日本銀行", "url": "https://www.boj.or.jp/rss/whatsnew.xml", "tier": "一次資料", "topic": "rates"},
]

TOPICS = {
    "ai": {"name": "AI・テック", "pattern": r"\bai\b|artificial intelligence|nvidia|semiconductor|meta|tesla|microsoft|alphabet|openai|半導体|人工知能|生成AI|決算|エヌビディア", "lesson": "ai", "question": "売上だけでなく、AI投資に見合う利益と資金繰りが出ているか。", "chain": ["決算・事業見通し", "将来の利益予想が変化", "株価の評価が変化"], "caution": "好決算でも、事前の期待を下回ると株価は下がることがあります。"},
    "energy": {"name": "原油・供給", "pattern": r"\boil\b|crude|opec|hormuz|energy|原油|石油|ホルムズ|エネルギー", "lesson": "oil", "question": "供給が本当に減るのか、それとも懸念だけが強まったのか。", "chain": ["供給不安", "原油・輸送費が上昇", "物価と企業利益を圧迫"], "caution": "供給回復や需要減速で、原油価格は反対方向にも動きます。"},
    "rates": {"name": "物価・金利", "pattern": r"\bfed\b|interest rate|inflation|central bank|treasury|cpi|pce|金利|日銀|物価|金融政策|利上げ|利下げ|国債", "lesson": "rates", "question": "景気が強いから金利が上がったのか、物価への不安なのか。", "chain": ["物価・中央銀行の情報", "将来の金利予想が変化", "債券・為替・株の評価が変化"], "caution": "長期金利は政策金利だけでなく、財政やインフレの不安でも動きます。"},
    "geopolitics": {"name": "戦争・外交", "pattern": r"war|iran|israel|russia|ukraine|ceasefire|sanction|tariff|イラン|イスラエル|ロシア|ウクライナ|停戦|関税|戦争|制裁", "lesson": "oil", "question": "物流・資源供給・制裁に実際の変化があるか。", "chain": ["外交・軍事情勢", "供給と安全性の見方が変化", "原油・金・株・通貨へ波及"], "caution": "ニュースの見出しだけでは、被害規模や政策の実施を確認できません。"},
    "crypto": {"name": "暗号資産", "pattern": r"bitcoin|ethereum|crypto|ビットコイン|暗号資産|仮想通貨|イーサリアム", "lesson": "crypto", "question": "資金流入・規制・金利のうち、何が変わったか。", "chain": ["資金の流れ・規制", "買いたい人と売りたい人が変化", "価格と変動幅が拡大"], "caution": "週末も取引され、株式と違う方向に動くこともあります。"},
    "economy": {"name": "景気・政治", "pattern": r"gdp|growth|employment|election|trade|economy|景気|経済|選挙|雇用|貿易|成長|財政", "lesson": "rates", "question": "景気への影響と物価への影響を分けて考えよう。", "chain": ["政策・経済指標", "需要と企業利益の予想が変化", "株・債券・通貨へ波及"], "caution": "良い経済指標が利上げ予想を強め、株価には逆風となる場合もあります。"},
}
