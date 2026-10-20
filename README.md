# insight

世界の市場を、理由から理解する。日本語の市場観測・学習ダッシュボードです。

## 内容

- 世界の株式、米国市場金利、為替、暗号資産、商品、AI企業の25指標
- 明日・3日・1週間の条件付き見通し、観測事実と反対シナリオ
- Polymarketの確率・期限・流動性・スプレッド・前回取得差
- NHK、BBC、Fed、ECB、日銀の見出し・公式発表、BLS経済指標カレンダー
- 6つの学習レッスン、確認クイズ、用語集、金利・原油の因果実験
- 観測後の方向一致検証、情報源の状態、欠測・古いデータの表示

特定人物の監修・公式サイトではありません。売買や投資助言の実行機能はありません。

## 公開

1. GitHubに **insight** リポジトリを作成し、ソースを `main` に配置します。
2. Settings → Pages → Build and deployment → Source を **GitHub Actions** にします。
3. Actions → **Observe markets and publish Pages** → Run workflow。
4. Actionsの `deploy` が成功すると、GitHubが返すPages URLで表示できます。

自動実行は **毎時17分** です。UTCのcronなのでJSTでも毎時17分です。GitHubの混雑による遅延や欠落があり、厳密な60分間隔は保証されません。公開リポジトリが60日間無活動の場合、定期実行が無効になる場合があります。

ユーザーが設定するAPIキーやSecretsは不要です。GitHubがジョブごとに発行する自動の `GITHUB_TOKEN` を、チェックアウトとデータ用ブランチへの保存、Pagesデプロイに使用します。外部ニュースは公開RSSの見出しとリンクのみで、本文を複製しません。

## ローカル実行（Python 3.12.14）

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v
python scripts/update.py
python scripts/build.py
```

標準ライブラリだけで動き、pipインストールは不要です。`dist/index.html` はCSS・JS・初期データを含む単独HTMLなので直接開けます。ファイルとして開いた場合は保存時点のデータです。公開Pagesでは5分おきに最新の公開JSONを確認します。

## 構成

| ファイル | 内容 |
| --- | --- |
| `site/index.html` | 画面構造 |
| `site/assets/style.css` | レスポンシブデザイン |
| `site/assets/app.js` | チャート・絞り込み・解説・学習 |
| `scripts/config.py` | 銘柄・ニュース取得先・因果説明 |
| `scripts/update.py` | 取得・解析・スナップショット・検証集計 |
| `scripts/build.py` | 単独HTMLと公開JSONを生成 |
| `scripts/history_branch.py` | `insight-data` ブランチに観測履歴を保存 |
| `site/data/learn.json` | 日本語教材 |
| `site/data/events.json` | 一次資料で確認した個別予定 |
| `.github/workflows/observe.yml` | 毎時更新とPages公開 |

毎時の観測データは `insight-data` ブランチの `snapshot.json` と `history.json` に保存します。ソースの `main` は書き換えません。履歴は45日分。初期 `site/data/snapshot.json` は初回表示用で、公開時には毎回更新されます。

## 分析の正確な位置づけ

これは、透明なルールと取得した観測値を使う教材型ダッシュボードです。外部LLMによる記事全文分析や、検証済みの価格予測モデルではありません。

- スコア：過去5取引日と前日の変動を日次標準偏差で割って合成。±18以上を方向ありとする任意ルール。確率ではありません。
- 価格帯：過去最大60日の日次変動から計算する振れ幅の参考値。中心は現在値。将来の68%予測区間ではありません。
- 金利：米国市場の利回りです。政策金利や実質金利と区別。利回りの変化をbpで表示。
- ニュース：見出しからテーマを分類し、一般的な経済のつながりを示します。本文からイベントの発生・方向・規模を自動認定しません。
- Polymarket：イベントの市場価格を観測。資産価格スコアには加算せず、将来の株価上昇確率に読み替えません。
- 取得失敗：元の観測時刻を保った前回値を表示し、方向評価から除外。初回欠測に仮の価格を入れません。
- 予定：BLSは毎時取得。個別企業・日本の予定は明示した確認日付きの固定予定で、期限後は非表示です。翌週以降の企業予定を無制限に自動網羅するものではありません。
- 取引時間：土日以外の各国祝日は未調整。先物の限月交代にも注意。
- 検証：保存後の観測についてだけ集計。各銘柄・起点日1件、横ばい・方向なしを除外。複数資産の相関や期間重複があるため独立試行ではありません。取引コスト・収益の検証ではありません。

## 保守

API・RSSが変更されたら `scripts/config.py` と `scripts/update.py` を修正します。価格はYahooの公開チャートを利用するため、レート制限や仕様変更があり得ます。403/429を回避するアクセスは行いません。取得状態は画面の「データと読み方」とActionsログで確認できます。

## 参考

- [Polymarket Gamma API](https://docs.polymarket.com/api-reference/markets/list-markets)
- [FedのRSS](https://www.federalreserve.gov/feeds/feeds.htm)
- [BLS発表日程](https://www.bls.gov/schedule/)
- [GitHub scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [GitHub Pagesのカスタムワークフロー](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

第三者のデータ・見出しの権利は各提供元に帰属します。再配布や商用利用は提供元の条件を確認してください。
