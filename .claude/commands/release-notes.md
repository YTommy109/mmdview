# /release-notes — リリースノート生成

前回タグからのコミットを元にリリースノートを生成する。

## 1. タグの取得

```bash
git tag --sort=-v:refname | head -2
```

- 最新タグと前回タグを取得する
- タグが 1 つしかない場合は初回リリースとして全コミットを対象にする

## 2. コミットログの取得

```bash
git log {前回タグ}..{最新タグ} --pretty=format:"%s" --no-merges
```

## 3. リリースノートの生成

Conventional Commits のプレフィックスでグループ化して Markdown 形式で出力する:

```markdown
## {最新タグ}

### Features
- 項目（feat: から）

### Bug Fixes
- 項目（fix: から）

### Others
- 項目（上記以外）
```

該当がないグループは省略する。
