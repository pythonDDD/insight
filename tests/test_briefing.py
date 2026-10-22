"""The briefing must not turn an unrelated, stale or denied headline into a fact."""
import copy
import datetime as dt
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from briefing import create_briefing, fresh_quote, profile


NOW = dt.datetime(2026, 10, 22, 12, tzinfo=dt.timezone.utc)


class BriefingChecks(unittest.TestCase):
    def news(self, key, title, hours=1, **extra):
        return {"id": key, "title": title, "url": "https://example.com/" + key,
                "source": "テスト用報道", "tier": "報道", "status": "ok",
                "publishedAt": (NOW - dt.timedelta(hours=hours)).isoformat(), **extra}

    def quote(self, **extra):
        return {"id": "nikkei", "name": "日経平均", "price": 100, "group": "equity",
                "changePct": -2, "sigma": 1, "score": -30, "status": "ok", "stale": False,
                "observedAt": (NOW - dt.timedelta(hours=1)).isoformat(), **extra}

    def test_three_distinct_themes_not_three_copies_of_a_story(self):
        news = [self.news("a", "メタ決算 AI投資が利益を圧迫"),
                self.news("b", "テスラ決算 大幅減益", hours=.5),
                self.news("c", "日銀 金利を据え置き"),
                self.news("d", "イランへの攻撃計画 報道")]
        result = create_briefing(news, [], NOW)
        self.assertEqual(len(result["stories"]), 3)
        self.assertEqual({s["theme"] for s in result["stories"]}, {"rates", "energy", "tech"})
        self.assertEqual(result, create_briefing(list(reversed(news)), [], NOW))

    def test_stale_cached_future_or_unsafe_articles_do_not_fill_empty_slots(self):
        title = "日銀 金利据え置き"
        news = [self.news("fresh", title), self.news("old", title, hours=49),
                self.news("future", title, hours=-.01), self.news("cache", title, status="cached"),
                self.news("unsafe", title, url="javascript:alert(1)"),
                self.news("auth", title, url="https://user:password@example.com/")]
        result = create_briefing(news, [], NOW)
        self.assertEqual([s["id"] for s in result["stories"]], ["fresh"])
        self.assertEqual(result["status"], "limited")
        self.assertEqual(create_briefing([], [], NOW)["stories"], [])

    def test_market_connection_outranks_generic_company_news(self):
        news = [self.news("connected", "日経平均の下落招いたメタの財務不安", hours=4),
                self.news("newer", "テスラ 統合計画を発表", hours=1)]
        result = create_briefing(news, [self.quote()], NOW)
        self.assertEqual(result["stories"][0]["id"], "connected")
        self.assertEqual(result["stories"][0]["assetIds"], ["nikkei", "meta"])

    def test_denials_and_speculation_never_become_confirmed_events(self):
        hold = profile("日銀 利上げ見送りへ")
        hike = profile("日銀 利上げを決定")
        self.assertEqual(hold["summary"], hike["summary"])
        self.assertIn("なら", hold["summary"])
        for title in ["イラン攻撃計画を否定", "イラン停戦合意せず", "イラン停戦への期待"]:
            p = profile(title)
            self.assertIn("滞れば", p["summary"])
            self.assertNotIn("供給が止まった", p["summary"])

    def test_keywords_in_unrelated_headlines_are_not_catalysts(self):
        for title in ["香港の住宅火災 調査報告書を提出", "AI活用ルール整理へ",
                      "Woman scared to turn heating on due to oil cost",
                      "第一生命が金投資、インフレ対策で分散運用拡大 相場に押し上げ効果",
                      "Chair describes investment in local schools"]:
            self.assertIsNone(profile(title), title)

    def test_failed_stale_future_and_nan_quotes_are_not_evidence(self):
        self.assertTrue(fresh_quote(self.quote(), NOW))
        for changes in [{"status": "cached"}, {"stale": True}, {"price": float("nan")},
                        {"observedAt": (NOW - dt.timedelta(hours=97)).isoformat()},
                        {"observedAt": (NOW + dt.timedelta(hours=1)).isoformat()},
                        {"observedAt": None},
                        {"group": "crypto", "observedAt": (NOW - dt.timedelta(hours=31)).isoformat()}]:
            self.assertFalse(fresh_quote(self.quote(**changes), NOW))
        news = [self.news("a", "日経平均の下落招いたメタの財務不安")]
        baseline = create_briefing(news, [], NOW)["stories"][0]["selectionScore"]
        with_failed = create_briefing(news, [self.quote(status="cached")], NOW)["stories"][0]
        self.assertEqual(with_failed["selectionScore"], baseline)

    def test_news_selection_does_not_mutate_price_scores(self):
        assets = [self.quote()]
        before = copy.deepcopy(assets)
        create_briefing([self.news("a", "日経平均の下落招いたメタの財務不安")], assets, NOW)
        self.assertEqual(assets, before)

    def test_price_report_is_labelled_as_observation_not_an_explanation(self):
        p = profile("日経平均が急落")
        self.assertEqual(p["kind"], "market-observation")
        self.assertIn("何が原因だったかまでは決まりません", p["summary"])


if __name__ == "__main__":
    unittest.main()
