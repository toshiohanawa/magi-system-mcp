# MAGI Consensus Mode - Unified Persona Template & Judge Template

## 概要

MAGIシステムのConsensusモードでは、3つのペルソナ（MELCHIOR、BALTHASAR、CASPAR）が並列で提案を評価し、最終的な判定を生成します。本ドキュメントでは、統一ペルソナテンプレート（UPT）とJudge JSON仕様について説明します。

---

## 統一ペルソナテンプレート（Unified Persona Template, UPT）

### 仕様

すべてのペルソナは、以下の厳密な出力フォーマットに従う必要があります：

```
VOTE: YES | NO | CONDITIONAL

REASON:
- 箇条書きで具体的理由を列挙

OPTIONAL_NOTES:
- 必要なら補足を書く（なければ空欄でよい）
```

### 制約事項

1. **行頭の固定キーワード**: `VOTE:`, `REASON:`, `OPTIONAL_NOTES:` は行頭に配置し、大文字小文字を区別しない
2. **あいさつ文禁止**: 自然言語のあいさつや説明文は一切禁止
3. **前後の自然文禁止**: フォーマット以外のテキストは出力しない
4. **順序の柔軟性**: VOTE/REASON/OPTIONAL_NOTESの順序が異なってもパース可能（ただし推奨順序は上記）

### テンプレート構造

各ペルソナテンプレートには以下のプレースホルダーが含まれます：

- `{proposal}`: 評価対象の提案
- `{persona_override}`: 追加プロファイル（指定がない場合は「（追加プロファイルなし）」）

### ペルソナ別の評価基準

#### MELCHIOR (科学者)
- **役割**: 論理的整合性・技術的正確性・仕様との整合性を評価
- **評価基準**:
  - 論理的整合性
  - 技術的正確性
  - 仕様との整合性
  - 実装可能性
- **注意**: 安全性、セキュリティ、実用性、時間的制約は評価しない

#### BALTHASAR (安全性)
- **役割**: 安全性・セキュリティ・安定性・保守性・リスクを最優先で評価
- **評価基準**:
  - セキュリティリスク（SQLインジェクション、XSS、認証・認可）
  - 安定性（エラーハンドリング、例外処理、エッジケース）
  - 保守性（コードの可読性、テスト可能性、ドキュメント）
  - リスク（将来の技術的負債、拡張性）
- **注意**: 実装の速度や効率は評価しない

#### CASPAR (実用主義者)
- **役割**: 実用性・速度・「今動くこと」・ユーザー目標の達成を最優先
- **評価基準**:
  - 実用性
  - 速度
  - 目標達成
  - 実装の容易さ
- **注意**: 軽微な技術的負債やルール違反は、結果が有用であれば許容

---

## persona_override の利用方法

### 概要

`persona_override` は、各ペルソナに追加の評価基準や指示を提供するための機能です。

### 使用方法

```python
from magi.consensus import MagiConsensusEngine
from magi.models import Persona

# persona_overridesを指定
persona_overrides = {
    Persona.MELCHIOR: "このプロジェクトではPython 3.11以上を必須とする",
    Persona.BALTHASAR: "GDPR準拠を最優先で確認すること",
    Persona.CASPAR: "MVPとして2週間以内にリリース可能な範囲で評価",
}

decision = await engine.evaluate(
    proposal="新しい認証システムの実装",
    criticality="NORMAL",
    persona_overrides=persona_overrides,
)
```

### テンプレート内での表示

`persona_override` が指定されていない場合、テンプレート内では「（追加プロファイルなし）」が表示されます。

---

## パースロジックの堅牢性

### 正規表現パターン

パースロジックは以下の正規表現を使用して、LLM出力の揺らぎに耐性を持たせています：

1. **VOTE抽出**: `r"VOTE:\s*(YES|NO|CONDITIONAL)"` (大文字小文字不問)
2. **REASON抽出**: `r"REASON:\s*(.+?)(?:\n\s*OPTIONAL_NOTES:|$)"` (複数行対応)
3. **OPTIONAL_NOTES抽出**: `r"OPTIONAL_NOTES:\s*(.+?)(?:\n\s*(?:VOTE|REASON):|$)"` (オプショナル)

### 揺らぎ耐性

以下のケースでも正しくパースされます：

- **順序の違い**: REASONがVOTEの前に来ても動作
- **余分な空白**: タブや複数のスペースがあっても動作
- **OPTIONAL_NOTES欠落**: OPTIONAL_NOTESがなくても動作
- **大文字小文字**: すべて小文字でも動作

### エラーハンドリング

パースに失敗した場合：
- VOTEが抽出できない → `Vote.NO` を返し、エラーメッセージをreasonに設定
- REASONが抽出できない → フォールバックとしてVOTE以降のテキストを使用
- OPTIONAL_NOTESが抽出できない → `None` を返す（エラーではない）

---

## MagiDecision のJSON構造仕様

### データ構造

```python
@dataclass
class PersonaResult:
    persona: Persona  # "melchior" | "balthasar" | "caspar"
    vote: Vote  # "YES" | "NO" | "CONDITIONAL"
    reason: str
    optional_notes: Optional[str]  # None または文字列

@dataclass
class MagiDecision:
    decision: Decision  # "APPROVED" | "REJECTED" | "CONDITIONAL"
    risk_level: RiskLevel  # "LOW" | "MEDIUM" | "HIGH"
    persona_results: List[PersonaResult]
    aggregate_reason: str
    suggested_actions: List[str]
```

### JSONシリアライズ例

```json
{
  "decision": "APPROVED",
  "risk_level": "MEDIUM",
  "persona_results": [
    {
      "persona": "melchior",
      "vote": "YES",
      "reason": "- 技術的に正しい実装\n- 仕様と整合している",
      "optional_notes": "パフォーマンステストを推奨"
    },
    {
      "persona": "balthasar",
      "vote": "YES",
      "reason": "- セキュリティリスクなし\n- エラーハンドリングが適切",
      "optional_notes": null
    },
    {
      "persona": "caspar",
      "vote": "CONDITIONAL",
      "reason": "- 実用的な解決策\n- 実装が容易",
      "optional_notes": "キャッシュの追加を検討"
    }
  ],
  "aggregate_reason": "Approved. Score: 0.85. Some personas have conditions.",
  "suggested_actions": [
    "Add caching as suggested",
    "Consider performance testing"
  ]
}
```

---

## テスト方針

### テストケース

1. **test_persona_override_applied**: override付きでテンプレートが正しく生成される
2. **test_parse_format_order_tolerance**: VOTE/REASON/OPTIONAL_NOTESの順序が異なっても正しくパース
3. **test_parse_optional_notes_missing**: OPTIONAL_NOTESが欠けても壊れない
4. **test_parse_extra_whitespace**: 余分な空白があってもパース成功
5. **test_magi_decision_json_structure**: MagiDecisionがJSON形式で正しくシリアライズ
6. **test_fallback_format_consistency**: フォールバック後もフォーマット一貫性を維持

### テスト実行

```bash
pytest tests/test_consensus.py -v
```

---

## 既存実装からの差分

### 主な変更点

1. **統一フォーマット**: 3ペルソナすべてが同じ出力フォーマット（UPT）を使用
2. **OPTIONAL_NOTES追加**: PersonaResultにoptional_notesフィールドを追加
3. **persona_override対応**: カスタムペルソナプロファイルの指定が可能
4. **パース強化**: 正規表現ベースの堅牢なパースロジック
5. **JSON互換性**: MagiDecisionがJSON形式でシリアライズ可能

### 後方互換性

- 既存のAPI呼び出しはそのまま動作（persona_overridesはオプショナル）
- OPTIONAL_NOTESがない場合、Noneが返される
- 既存のテストは更新済み（_parse_vote_and_reason → _parse_persona_output）

---

## 実装ファイル

- `src/magi/personas.py`: 統一ペルソナテンプレート定義
- `src/magi/prompt_builder.py`: プロンプト生成（override対応）
- `src/magi/consensus.py`: パースロジックと評価エンジン
- `src/magi/models.py`: PersonaResult（optional_notes追加）
- `tests/test_consensus.py`: テストケース

---

## 参考

- [MAGI Consensus Engine](../src/magi/consensus.py)
- [Persona Definitions](../src/magi/personas.py)
- [Prompt Builder](../src/magi/prompt_builder.py)

