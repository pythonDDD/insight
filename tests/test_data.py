"""Meaningful checks for financial units, time windows, and degraded data."""
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update as app


class DataChecks(unittest.TestCase):
    def market(self, **kwargs):
        return {"id":"1","question":"Will the Fed lower interest rates this week?", "active":True,
                "closed":False,"acceptingOrders":True, "endDate":app.iso(app.WINDOW_START+dt.timedelta(days=1)),
                "outcomes":'["No", "Yes"]',"outcomePrices":'["0.3", "0.7"]',"liquidityNum":100000,
                "volume24hr":25000,"spread":.01,"slug":"test",**kwargs}

    def test_yes_is_selected_by_label_not_position(self):
        m=app.normalize_market(self.market(),{})
        self.assertEqual(m["probability"],.7)
        self.assertIsNone(m["changePp"])

    def test_probability_changes_are_percentage_points(self):
        old={"1":{"probability":.6,"fetchedAt":app.iso(app.NOW-dt.timedelta(hours=1))}}
        self.assertAlmostEqual(app.normalize_market(self.market(),old)["changePp"],10)

    def test_expired_today_far_future_and_untradeable_contracts_excluded(self):
        for override in ({"endDate":app.iso(app.NOW-dt.timedelta(hours=1))},
                         {"endDate":app.iso(app.WINDOW_START-dt.timedelta(seconds=1))},
                         {"endDate":app.iso(app.NOW+dt.timedelta(days=365))},
                         {"closed":True},{"acceptingOrders":False}):
            with self.subTest(override=override):self.assertIsNone(app.normalize_market(self.market(**override),{}))

    def test_low_liquidity_and_malformed_probabilities_rejected(self):
        for override in ({"liquidityNum":200},{"outcomePrices":'["NaN","0.4"]'},
                         {"outcomePrices":'["1.1","-0.1"]'},{"outcomePrices":'["0.4"]'}):
            self.assertIsNone(app.normalize_market(self.market(**override),{}))

    def test_ics_hyphenated_timezone_and_dst(self):
        day=(app.WINDOW_START+dt.timedelta(days=1)).astimezone(app.ZoneInfo("America/New_York"))
        when=day.replace(hour=8,minute=30,second=0,microsecond=0)
        text=f"BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART;TZID=US-Eastern:{when.strftime('%Y%m%dT%H%M%S')}\nSUMMARY:CPI\nEND:VEVENT\nEND:VCALENDAR"
        parsed=app.parse_ics(text)
        self.assertEqual(len(parsed),1)
        self.assertEqual(app.parse_time(parsed[0]["at"]),when.astimezone(app.UTC))

    def test_future_and_old_news_do_not_enter_current_feed(self):
        dates=[app.NOW-dt.timedelta(hours=2),app.NOW+dt.timedelta(days=1),app.NOW-dt.timedelta(days=10)]
        xml='<rss><channel>'+''.join(f'<item><title>Fed news {i}</title><link>https://example.com/{i}</link><pubDate>{app.iso(d)}</pubDate></item>' for i,d in enumerate(dates))+'</channel></rss>'
        result=app.parse_feed(xml,{"id":"test","name":"Test","topic":"rates","tier":"一次資料"})
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["title"],"Fed news 0")

    def test_non_https_link_not_published(self):
        self.assertEqual(app.safe_url("javascript:alert(1)"),"")
        self.assertEqual(app.safe_url("https://u:secret@example.com/"),"")

    def test_yield_changes_use_basis_points_and_previous_day_not_range_start(self):
        now=app.NOW.replace(hour=12,minute=0,second=0,microsecond=0)
        timestamps=[int((now-dt.timedelta(days=25-i)).timestamp()) for i in range(26)]
        closes=[4.0+i*.01 for i in range(26)]
        payload={"chart":{"result":[{"meta":{"regularMarketPrice":4.30,"regularMarketTime":now.timestamp(),"chartPreviousClose":3.0,"exchangeTimezoneName":"UTC"},"timestamp":timestamps,"indicators":{"quote":[{"close":closes}]}}]}}
        with patch.object(app,"NOW",now+dt.timedelta(minutes=1)),patch.object(app,"fetch",return_value=payload):
            q=app.get_quote(("us10y","Treasury","US","^TNX","rates","PCT","yield"))
        self.assertAlmostEqual(q["previous"],4.24)
        self.assertAlmostEqual(q["changeBps"],6)
        self.assertTrue(-100<=q["score"]<=100)

    def test_failed_fetch_retains_time_and_excludes_from_outlook(self):
        past=app.iso(app.NOW-dt.timedelta(hours=2))
        previous={"assets":[{"id":"sp500","name":"S&P","group":"equity","unit":"index","price":100,"score":80,"observedAt":past,"fetchedAt":past,"history":[]}]}
        with patch.object(app,"get_quote",side_effect=RuntimeError("offline")):
            quotes,status=app.collect_quotes(previous)
        q=quotes[0]
        self.assertEqual(q["observedAt"],past)
        self.assertEqual(q["fetchedAt"],past)
        self.assertEqual(q["status"],"cached")
        self.assertFalse(app.usable(q))
        self.assertEqual(status["count"],0)
        self.assertIsNone(app.create_outlooks(quotes,[],[])[0]["score"])

    def test_first_observation_has_no_invented_accuracy_and_hour_is_deduplicated(self):
        with tempfile.TemporaryDirectory() as td,patch.object(app,"DATA",Path(td)):
            q={"id":"sp500","group":"equity","unit":"index","price":100,"score":30,"observedAt":app.iso(),"status":"ok","stale":False}
            first=app.update_history([q]);second=app.update_history([q])
            self.assertEqual(second["snapshotCount"],1)
            self.assertTrue(all(s["hitRate"] is None for s in first["stats"]))


if __name__=="__main__":unittest.main()
