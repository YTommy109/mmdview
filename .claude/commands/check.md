# /check — 品質チェック

以下を順番に実行して結果を報告してください。

1. **ビルド**
   ```bash
   cd MmdviewApp && swift build
   ```

2. **Swift テスト**
   ```bash
   cd MmdviewApp && swift test
   ```

3. **JS テスト**
   ```bash
   cd MmdviewApp && npx jest
   ```

問題が見つかった場合は修正してから再実行してください。すべて通過したら「✅ チェック完了」と報告してください。
