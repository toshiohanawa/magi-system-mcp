# Verbose情報が返らない問題のデバッグ

## 問題

`verbose: true`をリクエストに含めているにもかかわらず、レスポンスで`logs`、`summary`、`timeline`が`None`になっている。

## リクエストJSON

```json
{
  "initial_prompt": "テストプロンプト",
  "mode": "proposal_battle",
  "verbose": true
}
```

## レスポンスJSON（構造のみ）

```json
{
  "session_id": "...",
  "results": {
    "codex": {
      "model": "codex",
      "content": "...",
      "metadata": {
        "status": "ok",
        "cli_type": "real",
        "cli_path": "http://host.docker.internal:9001",
        "trace_id": "..."
      }
    },
    "claude": {...},
    "gemini": {...}
  },
  "logs": null,
  "summary": null,
  "timeline": null
}
```

## 確認すべきポイント

1. **リクエストの`verbose`値**: `true`（boolean）が正しく送信されているか
2. **FastAPIのリクエストパース**: `StartRequest.verbose`が正しく`True`として解釈されているか
3. **コントローラーの`verbose_flag`計算**: `verbose_flag = self.verbose_default if verbose is None else verbose`が正しく動作しているか
4. **`proposal_battle.run()`への`verbose`引数**: `verbose_flag`が正しく渡されているか
5. **`_call_with_trace()`内の`verbose`チェック**: `if verbose:`が正しく評価されているか
6. **レスポンス構築時の`verbose_flag`チェック**: `logs if verbose_flag else None`が正しく動作しているか

## デバッグ手順

1. `/tmp/debug_request.json`と`/tmp/debug_response_full.json`を確認
2. サーバーログで`verbose`値の流れを追跡
3. `controller.py`の`start_magi`メソッドにデバッグログを追加
4. `proposal_battle.py`の`run`メソッドにデバッグログを追加

## 実装上の確認事項

### controller.py (33行目)
```python
verbose_flag = self.verbose_default if verbose is None else verbose
```
- `verbose`が`None`でない場合、`verbose`の値を使用
- `verbose`が`True`なら`verbose_flag`も`True`になるはず

### controller.py (45-47行目)
```python
"logs": logs if verbose_flag else None,
"summary": summary if verbose_flag else None,
"timeline": timeline if verbose_flag else None,
```
- `verbose_flag`が`True`なら、`logs`、`summary`、`timeline`が返されるはず
- `verbose_flag`が`False`なら、`None`が返される

### proposal_battle.py (30行目)
```python
async def run(self, task: str, verbose: bool = False) -> tuple[Dict[str, ModelOutput], list, str, list[str]]:
```
- `verbose`パラメータが正しく渡されているか確認

### proposal_battle.py (116-136行目)
```python
if verbose:
    timeline.append(f"[start] {step} (trace_id={trace_id})")
...
if verbose:
    status = output.metadata.get("status", "unknown")
    ...
    self._append_log_entry(...)
    timeline.append(self._render_timeline_step(...))
```
- `verbose`が`True`の場合、`logs`と`timeline`に追加されるはず

## 次のステップ

実際のリクエストとレスポンスを確認し、どの段階で`verbose`が`False`になっているかを特定する。

