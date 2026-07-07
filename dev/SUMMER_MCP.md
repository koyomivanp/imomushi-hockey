# Summer MCP 接続確認スクリプト

PowerShell で実行:

```powershell
.\dev\test_summer_mcp.ps1
```

## 手動で MCP をオンラインにする

1. `npx -y summer-engine@latest doctor` → MCP Server: ready を確認
2. Summer Engine アプリを起動（タスクバーに Summer が出るまで待つ）
3. **Cursor を完全終了して再起動**
4. Cursor Settings → MCP → `summer-engine` が **connected** か確認
5. 無効なら **Restart** をクリック

## 設定ファイル

- ユーザー: `C:\Users\tocha\.cursor\mcp.json`
- プロジェクト: `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "summer-engine": {
      "command": "npx",
      "args": ["-y", "summer-engine@latest", "mcp"]
    }
  }
}
```

## 画像生成（芋虫ホッケー）

MCP 接続後、チャットで:

> `summer_generate_image` で art-bible の battle_bg プロンプトを使って画像を生成して

生成 PNG は `assets/arena/` に配置。
