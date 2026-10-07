# task-view の決まりごと

- これは**仕事の環境で使う道具の試作**。「仕事の環境ならこんなものを作りたい」というたたき台で、今の仕様に縛られなくてよい。
- **業務データを持ち込まない。** データは `sample-data/` の架空のダミーだけ。実在の会社名・人名・案件名・チケット番号は書かない。
- 仕事の環境の前提（今わかっている範囲）: Python 標準ライブラリだけ・外部パッケージなし・ローカルだけで動く（`127.0.0.1`）。クラウドの AI に業務データを貼らない。
- `タスク一覧.md` は、仕事の環境で Claude が会議・録音・メモから書き起こして更新している（推測は「要確認」と書く運用）。ビューはそれを読むだけ。
- `.bat` は中身を ASCII のみ・CRLF 改行にする（日本語や LF だと cmd が誤動作した）。
- 画面は `innerHTML` を使わず、`textContent` 系で描画する。
- `app/taskview.py` を変えたら、サーバーを止めて起動し直してから確認する。
- GitHub で公開している: https://github.com/sir0oo/task-view （公開リポジトリ。会社の PC には zip で入れる）。中身は誰でも見られるので、業務データ・個人情報・Artifact のリンクを書かない。
- 公開版の更新手順（モノレポの `G:\Claude` で、task-view の変更をコミットしてから）:
  `git subtree split --prefix=projects/task-view -b task-view-export` → `git push https://github.com/sir0oo/task-view.git task-view-export:main`
- `.bat` は `.gitattributes` の `*.bat -text` で CRLF のまま保存している。新しい .bat も CRLF で作る。
