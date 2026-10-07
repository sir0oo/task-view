"""期限と印の読み取りのテスト。  python -m unittest discover tests"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from taskview import _has_flag, parse_due, parse_original_due  # noqa: E402

REF = date(2026, 10, 7)


class ParseDue(unittest.TestCase):
    def check(self, raw, expected, kind):
        self.assertEqual(parse_due(raw, REF), (expected, kind), raw)

    def test_day_forms(self):
        for raw in ["10/9", "１０/９", "10/9(金)", "10/9まで", "10/9 15:00", "2026-10-09", "2026/10/9", "10月9日"]:
            self.check(raw, date(2026, 10, 9), "day")

    def test_month_forms(self):
        self.check("10月中", date(2026, 10, 31), "month")
        self.check("11月末", date(2026, 11, 30), "month")
        self.check("11月", date(2026, 11, 30), "month")
        self.check("10月上旬", date(2026, 10, 10), "month")
        self.check("10月中旬", date(2026, 10, 20), "month")
        self.check("10月下旬", date(2026, 10, 31), "month")

    def test_year_roll(self):
        self.check("1/15", date(2027, 1, 15), "day")
        self.check("12/28", date(2026, 12, 28), "day")

    def test_undecided(self):
        for raw in ["来週", "レビュー返信後", "期限未設定", "", "2/30", "13月"]:
            self.check(raw, None, "none")

    def test_extension(self):
        self.check("レビュー返信後（旧：10/2）", None, "none")
        self.assertEqual(parse_original_due("レビュー返信後（旧：10/2）", REF), ("10/2", date(2026, 10, 2)))
        self.check("10/12（旧：10/9）", date(2026, 10, 12), "day")


class Flags(unittest.TestCase):
    def test_flag_at_head(self):
        self.assertTrue(_has_flag("要確認", "", "要確認：旧仕様書に抜けがある"))
        self.assertTrue(_has_flag("要確認", "", "2営業日以内に出す。要確認：会議の日程"))
        self.assertTrue(_has_flag("要確認", "", "要確認"))
        self.assertTrue(_has_flag("待ち", "", "待ち：佐藤さんのレビュー枠"))

    def test_word_inside_sentence_is_not_flag(self):
        self.assertFalse(_has_flag("待ち", "", "承認待ちの流れを説明する"))
        self.assertFalse(_has_flag("待ち", "待ち時間の短縮案を作る", ""))
        self.assertFalse(_has_flag("要確認", "", "要確認事項の一覧を作る"))


class Discover(unittest.TestCase):
    """親フォルダを読むとき、task-view 自身の見本データは混ぜない。"""

    def test_parent_root_skips_own_samples(self):
        from taskview import HERE, discover
        own = HERE.parent
        self.assertFalse(any(own in p.resolve().parents for p in discover(own.parent)))

    def test_sample_root_still_reads_samples(self):
        from taskview import HERE, discover
        self.assertEqual(len(discover(HERE.parent / "sample-data")), 4)


if __name__ == "__main__":
    unittest.main()
