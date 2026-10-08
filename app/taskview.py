#!/usr/bin/env python3
"""案件フォルダの タスク一覧.md を読んで、期限ビューをブラウザに出すローカルツール。

- 読み取り専用。mdは書き換えない（--init の雛形作成のみ例外、既存ファイルは上書きしない）
- 標準ライブラリのみ。127.0.0.1 にだけバインドする
- 使い方:  python taskview.py            # 画面を開く
           python taskview.py --init 案件A   # その案件フォルダに雛形を作る
"""
from __future__ import annotations

import argparse
import calendar
import json
import re
import sys
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TASK_FILE = "タスク一覧.md"
HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[1]  # task-view/app/ -> task-view/ の親（仕事の環境では案件フォルダの親）
MAX_DEPTH = 3

TEMPLATE = """# {name}：タスク一覧（正本）

Claudeはこのフォルダで作業を始めるとき、まずこのファイルを読んで、自分の今のタスクと期限を把握する。
会議・やり取りで決まったことは、その場でここに反映する（まとめて後回しにしない）。

最終更新：{today}

## 更新のルール
- 新しいタスクが決まったら「進行中・今後のタスク」に追加する。由来（会議日・指示者）を必ず書く
- 期限が変わったら上書きせず、元の期限を「（旧：〜）」として残す
- 完了したら「完了」へ移し、完了日を書く
- 録音・メモから推測した内容は「要確認」と明記する
- このファイルは{name}のタスクだけを扱う。他案件のタスクは各案件フォルダで管理する
- グループ列には、案件内のプロジェクト名やチケット番号（例：PRJ-101）を書く。空欄でもよい
- 「待っている」「完了」の項目も同じグループに入れたいときは、先頭に【グループ名】を付ける（例：`- 2026-10-02：【PRJ-101】調査を完了`）

## 進行中・今後のタスク

| グループ | タスク | 期限 | 由来 | 状況・メモ |
|---|---|---|---|---|

## 他の人に待っている／他の人の宿題（把握用）

## 完了
"""


# ---------- 期限の解釈 ----------

def _end_of_month(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def _roll_year(d: date, ref: date) -> date:
    """基準日より半年以上前になる日付は翌年とみなす（年なし表記の補正）。"""
    if d < ref - timedelta(days=180):
        try:
            return d.replace(year=d.year + 1)
        except ValueError:  # 2/29
            return d.replace(year=d.year + 1, day=28)
    return d


def parse_due(raw: str, ref: date):
    """期限文字列 -> (date|None, 種別)。種別: day / month / none"""
    s = re.sub(r"[（(].*?[）)]", "", raw)  # 括弧内（旧：…）は現在の期限に含めない
    s = s.replace("**", "").strip()
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3])), "day"
    m = re.search(r"(\d{1,2})/(\d{1,2})", s)
    if m:
        try:
            return _roll_year(date(ref.year, int(m[1]), int(m[2])), ref), "day"
        except ValueError:
            return None, "none"
    m = re.search(r"(\d{1,2})月(\d{1,2})日", s)
    if m:
        try:
            return _roll_year(date(ref.year, int(m[1]), int(m[2])), ref), "day"
        except ValueError:
            return None, "none"
    m = re.search(r"(\d{1,2})月(上旬|中旬|下旬|末|中)?", s)
    if m and 1 <= int(m[1]) <= 12:
        end = _end_of_month(ref.year, int(m[1]))
        d = end.replace(day={"上旬": 10, "中旬": 20}.get(m[2] or "", end.day))
        return _roll_year(d, ref), "month"
    return None, "none"


def parse_original_due(raw: str, ref: date):
    """「（旧：10/9）」の中身を (表示用文字列, date|None) で返す。"""
    m = re.search(r"[（(]\s*旧[：:]\s*(.+?)\s*[）)]", raw)
    if not m:
        return None, None
    text = m[1].lstrip("〜~")
    d, _ = parse_due(text, ref)
    return text, d


# ---------- md の読み取り ----------

def _clean(s: str) -> str:
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)  # [text](path) -> text
    s = s.replace("**", "").replace("`", "")
    return s.strip()


def _split_group_tag(text: str) -> tuple[str, str]:
    """先頭の【グループ名】を取り出す。無ければ ("", 元の文字列)。"""
    m = re.match(r"\s*【(.+?)】\s*(.*)", text)
    return (m[1].strip(), m[2]) if m else ("", text)


def _has_flag(word: str, *texts: str) -> bool:
    """「要確認：」「待ち：」のように、文の頭でコロンが続くとき（または語だけのとき）だけ印とみなす（「承認待ちの件」は対象外）。"""
    pat = re.compile(r"(?:^|[。．、,\s/／])" + word + r"(?:[：:]|$)")
    return any(pat.search(_clean(t)) for t in texts)


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


DEFAULT_COLS = {"title": 0, "due": 1, "origin": 2, "memo": 3}
_COL_NAMES = {
    "title": ("タスク",),
    "due": ("期限",),
    "origin": ("由来",),
    "memo": ("状況・メモ", "メモ", "状況"),
    "group": ("グループ", "プロジェクト", "チケット"),
}


def _column_map(header: list[str]) -> dict[str, int]:
    cols = {}
    for key, names in _COL_NAMES.items():
        for i, h in enumerate(header):
            if h in names:
                cols[key] = i
                break
    for key, i in DEFAULT_COLS.items():  # 見出しが想定外でも落ちないよう既定位置で補う
        cols.setdefault(key, i)
    return cols


def _sections(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    cur = None
    for line in text.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def _find(sections: dict[str, list[str]], keyword: str) -> list[str]:
    for k, v in sections.items():
        if keyword in k:
            return v
    return []


def parse_task_file(path: Path, today: date) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"最終更新[：:]\s*(\d{4})-(\d{2})-(\d{2})", text)
    updated = date(int(m[1]), int(m[2]), int(m[3])) if m else None
    ref = updated or today
    sec = _sections(text)

    tasks = []
    cols = dict(DEFAULT_COLS)
    for line in _find(sec, "進行中"):
        if not line.lstrip().startswith("|"):
            continue
        cells = _split_row(line)
        if "タスク" in cells:  # 見出し行: 列の並びは見出し名で決める（グループ列は任意）
            cols = _column_map(cells)
            continue
        if len(cells) < 2 or all(re.fullmatch(r":?-+:?", c) for c in cells):  # 区切り行（|---|---|）
            continue
        cells += [""] * (max(cols.values()) + 1 - len(cells))

        def cell(key: str) -> str:
            i = cols.get(key)
            return cells[i] if i is not None and i < len(cells) else ""

        title, due_raw, origin, memo = cell("title"), cell("due"), cell("origin"), cell("memo")
        group = _clean(cell("group"))
        if not group:  # グループ列が無い／空なら、タイトル先頭の「名前：」を使う
            m_pre = re.match(r"^(.{1,24}?)[：:]\s*(.+)$", _clean(title))
            if m_pre:
                group, title = m_pre[1], m_pre[2]
        due, kind = parse_due(due_raw, ref)
        orig_text, orig_date = parse_original_due(due_raw, ref)
        if due is None:
            bucket, days = "undecided", None
        else:
            days = (due - today).days
            if due < today:
                bucket = "overdue"
            elif days <= 7:
                bucket = "week"
            elif (due.year, due.month) == (today.year, today.month):
                bucket = "month"
            else:
                bucket = "later"
        tasks.append({
            "group": group,
            "title": _clean(title),
            "due_label": _clean(re.sub(r"[（(].*?[）)]", "", due_raw)) or "未設定",
            "due": due.isoformat() if due else None,
            "due_kind": kind,
            "days_left": days,
            "bucket": bucket,
            "extended_from": orig_text,
            "extended": bool(orig_text) and (orig_date is None or due is None or orig_date != due),
            "origin": _clean(origin),
            "memo": _clean(memo),
            "needs_check": _has_flag("要確認", title, memo),
            "waiting": _has_flag("待ち", title, memo),
        })

    waiting = []
    for line in _find(sec, "待っている"):
        m2 = re.match(r"\s*[-*]\s*(.+)", line)
        if not m2:
            continue
        group, body = _split_group_tag(m2[1])
        m2b = re.match(r"(.+?)[：:]\s*(.+)", body)
        if m2b:
            waiting.append({"group": group, "who": _clean(m2b[1]), "text": _clean(m2b[2])})

    done = []
    for line in _find(sec, "完了"):
        m3 = re.match(r"\s*[-*]\s*(\d{4}-\d{2}-\d{2})[：:]\s*(.+)", line)
        if m3:
            group, body = _split_group_tag(m3[2])
            done.append({"group": group, "date": m3[1], "text": _clean(body)})
    done.sort(key=lambda x: x["date"], reverse=True)

    order = {"overdue": 0, "week": 1, "month": 2, "later": 3, "undecided": 4}
    tasks.sort(key=lambda t: (order[t["bucket"]], t["due"] or "9999"))
    return {"updated": updated.isoformat() if updated else None,
            "tasks": tasks, "waiting": waiting, "done": done}


def discover(root: Path) -> list[Path]:
    found = []
    own = HERE.parent  # task-view フォルダ自身（見本データ入り）
    skip_own = root.resolve() in own.parents  # root が task-view より上のときだけ除く
    for p in root.rglob(TASK_FILE):
        rel = p.relative_to(root)
        if skip_own and own in p.resolve().parents:  # 親フォルダを読むとき、見本データを本物に混ぜない
            continue
        if len(rel.parts) - 1 <= MAX_DEPTH and not any(x.startswith(".") for x in rel.parts):
            found.append(p)
    return sorted(found)


def build_payload(root: Path) -> dict:
    today = date.today()
    projects = []
    for p in discover(root):
        name = "/".join(p.relative_to(root).parts[:-1]) or root.name
        try:
            data = parse_task_file(p, today)
        except (OSError, UnicodeDecodeError, ValueError) as e:
            data = {"updated": None, "tasks": [], "waiting": [], "done": [], "error": str(e)}
        data["name"] = name
        data["file"] = str(p.relative_to(root)).replace("\\", "/")
        projects.append(data)
    return {"today": today.isoformat(), "weekday": "月火水木金土日"[today.weekday()],
            "generated": datetime.now().strftime("%H:%M:%S"), "projects": projects,
            "ui": (HERE / "index.html").stat().st_mtime_ns}  # 画面が古いまま開かれていたら、画面側で開き直す


# ---------- サーバー ----------

class Handler(BaseHTTPRequestHandler):
    root: Path = DEFAULT_ROOT

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/tasks":
            body = json.dumps(build_payload(self.root), ensure_ascii=False).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def log_message(self, *args):  # 静かに
        pass


def init_template(root: Path, folder: str) -> int:
    target = (root / folder).resolve()
    if root.resolve() not in target.parents and target != root.resolve():
        print("root の外には作れません。", file=sys.stderr)
        return 1
    if not target.is_dir():
        print(f"フォルダがありません: {target}", file=sys.stderr)
        return 1
    f = target / TASK_FILE
    if f.exists():
        print(f"すでにあります（上書きしません）: {f}")
        return 0
    f.write_text(TEMPLATE.format(name=target.name, today=date.today().isoformat()), encoding="utf-8")
    print(f"作成しました: {f}")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="タスク期限ビュー")
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="案件フォルダの親（既定: プロジェクト/）")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true", help="ブラウザを自動で開かない")
    ap.add_argument("--init", metavar="FOLDER", help="指定した案件フォルダに タスク一覧.md の雛形を作る")
    ap.add_argument("--dump", action="store_true", help="解析結果をJSONで標準出力に出して終了（確認用）")
    args = ap.parse_args()
    root = args.root.resolve()

    if args.init:
        return init_template(root, args.init)
    if args.dump:
        print(json.dumps(build_payload(root), ensure_ascii=False, indent=2))
        return 0

    Handler.root = root
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"タスクビュー: {url}  （Ctrl+C で終了）")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
