#!/usr/bin/env python3
"""ダミーの タスク一覧.md を sample-data/ に生成する。

期限は「実行した日」からの相対で作るので、いつ実行しても
期限切れ／7日以内／今月中／それ以降／期限未定 がまんべんなく出る。
実在の会社・人物・案件とは無関係の架空データ。

使い方:  python tools/gen_sample.py   （sample-data/ 内の案件A〜Dを作り直す。手で編集した分は上書きされる）
"""
from __future__ import annotations

import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "sample-data"
TODAY = date.today()

HEADER = """# {title}：サンプルのタスク一覧（架空データ）

最終更新：{today}

## 進行中・今後のタスク

| グループ | タスク | 期限 | 由来 | 状況・メモ |
|---|---|---|---|---|
"""


def md(n: int) -> str:
    """今日からn日後を M/D 表記で。"""
    d = TODAY + timedelta(days=n)
    return f"{d.month}/{d.day}"


def month_end(offset: int = 0, style: str = "中") -> str:
    """今月(offset=0)や来月以降の「N月中」「N月末」。"""
    y, m = TODAY.year, TODAY.month + offset
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{m}月{style}"


def ymd(n: int) -> str:
    return (TODAY + timedelta(days=n)).isoformat()


def render(title: str, tasks, waiting, done) -> str:
    out = HEADER.format(title=title, today=TODAY.isoformat())
    for g, t, due, origin, memo in tasks:
        out += f"| {g} | {t} | {due} | {origin} | {memo} |\n"
    out += "\n## 他の人に待っている／他の人の宿題（把握用）\n"
    out += "".join(f"- {w}\n" for w in waiting)
    out += "\n## 完了\n"
    out += "".join(f"- {d}\n" for d in done)
    return out


def case_a() -> str:
    tasks = [
        ("PRJ-101", "決済APIの仕様差分をまとめる", md(-3), "週次定例の宿題（田中さん）",
         "要確認：旧仕様書に抜けがある可能性。差分は表にして共有する"),
        ("PRJ-101", "テスト環境の接続情報を共有する", md(2), "キックオフ（佐藤さん指示）", "共有先は開発チーム全員"),
        ("PRJ-101", "リリース手順書のドラフトを作る", month_end(0, "中"), "週次定例",
         "待ち：佐藤さんのレビュー枠が未定。ドラフトは先に進めてよい"),
        ("PRJ-101", "本番切替の判断会議に出す資料を準備する", f"レビュー返信後（旧：{md(-5)}）",
         "田中さんの指示。期限はレビュー返信の遅れで延長", "返信が来たら2営業日以内に出す。要確認：会議の日程"),
        ("PRJ-101", "負荷試験の結果を整理する", "期限未設定", "週次定例", ""),
        ("運用改善", "障害対応の一次切り分けチェックリストを見直す", month_end(1, "末"), "鈴木さんの依頼", "現行版を元に差分だけ直す"),
        ("運用改善", "問い合わせ分類のタグ案を作る", md(10), "月次レビュー", ""),
        ("運用改善", "月次レポートの様式を決める", "期限未設定", "月次レビュー", "要確認：宛先が誰か未確定"),
        ("", "経費精算の申請", md(1), "自分で", ""),
    ]
    waiting = [
        "【PRJ-101】佐藤さん：仕様書の最新版の共有",
        "【PRJ-101】外部ベンダー：見積の回答",
        "【運用改善】鈴木さん：現行チェックリストの提供",
        "田中さん：来週の定例の議題出し",
    ]
    done = [
        f"{ymd(-1)}：【PRJ-101】要件一覧の初版を作成",
        f"{ymd(-6)}：【PRJ-101】キックオフに参加",
        f"{ymd(-4)}：【運用改善】現状の問い合わせ件数を集計",
        f"{ymd(-2)}：経費精算の前月分を申請",
    ]
    return render("案件A", tasks, waiting, done)


def case_b() -> str:
    long_title = ("配送ステータス更新APIのタイムアウト条件を確認し、アプリ側のリトライ仕様（回数・間隔・失敗時の画面表示）と"
                  "合わせて設計メモにまとめ、レビューに出す")
    tasks = [
        ("配送アプリ改修", long_title, md(5), "仕様レビュー", "要確認：タイムアウト値の根拠が資料にない"),
        ("配送アプリ改修", "通知文言の差し替え案を作る", md(0), "デザイン定例", "要確認：文字数の上限"),
        ("配送アプリ改修", "再配達依頼画面のワイヤーを直す", month_end(0, "中"), "デザイン定例", "要確認"),
        ("配送アプリ改修", "アクセシビリティ確認の観点を洗い出す", md(14), "鈴木さんの提案", "要確認：対象OSのバージョン"),
        ("配送アプリ改修", "リリースノートの雛形を作る", f"{month_end(1, '中')}（旧：{md(3)}）", "田中さん", "待ち：リリース日が未確定"),
        ("配送アプリ改修", "問い合わせ窓口の一覧を最新化する", "期限未設定", "自分で", "要確認"),
    ]
    waiting = ["【配送アプリ改修】デザイナー：最新のワイヤー", "【配送アプリ改修】佐藤さん：API仕様の確定"]
    done = [
        f"{ymd(-10)}：【倉庫システム移行】データ移行リハーサルを完了",
        f"{ymd(-8)}：【倉庫システム移行】切替当日の手順書を確定",
        f"{ymd(-3)}：【倉庫システム移行】本番切替が完了し、プロジェクトを終了",
    ]
    return render("案件B", tasks, waiting, done)


def case_c() -> str:
    """空の案件（空状態の表示確認用）。"""
    return render("案件C", [], [], [])


def case_d() -> str:
    """件数が多い案件（密度・スクロールの確認用）。4グループ×5件。"""
    groups = ["発注管理", "在庫連携", "帳票出力", "権限まわり"]
    spans = [-4, 0, 3, 6, 9, 15, 25, 40]
    tasks = []
    n = 0
    for g in groups:
        for i in range(5):
            n += 1
            kind = n % 8
            if kind == 0:
                due = "期限未設定"
            elif kind == 5:
                due = month_end(0, "中")
            elif kind == 6:
                due = "確認が取れてから"
            else:
                due = md(spans[n % len(spans)])
            memo = "要確認：前提の再確認が必要" if n % 3 == 0 else ("待ち：先方の回答待ち" if n % 7 == 0 else "")
            tasks.append((g, f"サンプルタスク{i + 1}（詳細を詰める）", due, "週次定例", memo))
    waiting = [f"【{g}】担当者{i}：資料の共有" for i, g in enumerate(groups, 1)]
    done = [f"{ymd(-i * 2)}：【{g}】サンプルの完了項目{i}" for i, g in enumerate(groups, 1)]
    return render("案件D（件数が多い）", tasks, waiting, done)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for name, body in [("案件A", case_a()), ("案件B", case_b()), ("案件C_空", case_c()), ("案件D_件数多", case_d())]:
        d = OUT / name
        if d.exists():
            shutil.rmtree(d)  # 生成対象の4フォルダだけ作り直す
        d.mkdir(parents=True)
        (d / "タスク一覧.md").write_text(body, encoding="utf-8")
        print("作成:", d / "タスク一覧.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
