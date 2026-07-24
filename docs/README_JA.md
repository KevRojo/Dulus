<div align="center">

<img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/dulus-bird.png" alt="Dulus — パームチャット" width="280">

<h1>DULUS</h1>

<h3>あなたの AI コンパニオン。チャットボットじゃない。そばを飛ぶ友達。</h3>

<p>
  <strong>API キーなしで最先端 AI を使用。$0。クレカ不要。サブスク不要。</strong>
</p>

<p>
  <a href="https://pypi.org/project/dulus/"><img src="https://img.shields.io/pypi/v/dulus.svg?style=flat-square&color=ff6b1f&labelColor=07070a&label=pypi" alt="PyPI"/></a>
  <a href="https://pypi.org/project/dulus/"><img src="https://static.pepy.tech/badge/dulus?style=flat-square" alt="Downloads"/></a>
  <img src="https://img.shields.io/badge/python-3.11+-ff6b1f?style=flat-square&labelColor=07070a" alt="Python"/>
  <img src="https://img.shields.io/badge/license-GPLv3-ff6b1f?style=flat-square&labelColor=07070a" alt="License"/>
  <img src="https://img.shields.io/badge/providers-100%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Providers"/>
  <img src="https://img.shields.io/badge/tools-30%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Tools"/>
  <img src="https://img.shields.io/badge/tests-263%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Tests"/>
  <a href="https://x.com/KevRojo"><img src="https://img.shields.io/badge/x-%40KevRojo-ff6b1f?style=flat-square&labelColor=07070a&logo=x" alt="X"/></a>
</p>

<p>
  <a href="#kuikkusutato"><b>クイックスタート</b></a> ·
  <a href="#kinou"><b>機能</b></a> ·
  <a href="#purobaida"><b>プロバイダ</b></a> ·
  <a href="#akitekucha"><b>アーキテクチャ</b></a> ·
</p>

</div>

---

> **パームチャット**（*Dulus dominicus*）にちなんで命名 —— ドミニカ共和国の国鳥、自由と韧性と共に飛ぶ象徴。Dulus はチャットボットではありません。そばを飛ぶ仲間、友達、AI パートナーです。

---

## なぜ Dulus か？

| | ロックされたエコシステム | 複雑なフレームワーク | **Dulus** |
|---|---|---|---|
| **セットアップ時間** | 数時間＋承認 | 数日の設定 | **30 秒** |
| **開始コスト** | $$$ + API キー | $$$ + インフラ | **$0** |
| **モデルロックイン** | 単一プロバイダ | 単一プロバイダ | **100+ プロバイダ** |
| **コードベース** | ブラックボックス | 100K+ 行 | **~56K 行のファーストパーティ Python** |
| **音声** | クラウドのみ | 含まれない | **オフライン Whisper** |
| **メモリ** | コンテキストのみ | 手動 | **MemPalace セマンティック** |

**問題：** 今日の AI エージェントは単一プロバイダにロックされているか、ML 工学の博士号が必要です。そしてすべてが試す前にクレジットカードを求めます。

**解決策：** Dulus。どんなモデルにも接続できる Python 自律エージェント —— 無料のブラウザセッション（Gemini guest、Claude.ai、Kimi、Qwen、DeepSeek）から LiteLLM 経由の 100+ 有料プロバイダ、ご自身のハードウェア上のローカルモデルまで。~56K 行のファーストパーティ Python。ビルドステップなし。ゲートキーピングなし。爪だけ。

---

## クイックスタート

### 30 秒インストール

```bash
pip install dulus && dulus
```

以上です。初回実行時、Dulus はブラウザを開き、**Gemini guest セッション**をキャプチャします（ログイン不要、API キー不要、クレカ不要）。30 秒以内に最先端 AI とチャットできます。

### ワンライナーインストール（推奨）

```bash
curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh | bash
```

### Docker（ローカル設定ゼロ）

```bash
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/.env.example
mv .env.example .env
docker compose up -d
```

---

## 機能

| 機能 | 説明 |
|---|---|
| マルチプロバイダ | 11 ネイティブ + LiteLLM 経由 100+ |
| ゼロ API キー | 無料ブラウザセッションをキャプチャ |
| 30+ 内蔵ツール | ファイル、シェル、Web、OCR、音声など |
| オートアダプター | 任意の Python リポをプラグインとしてインストール |
| MemPalace | ChromaDB によるセマンティックメモリ |
| 音声 I/O | Whisper によるオフライン STT。マルチエンジン TTS |
| サブエージェント | 分離された git worktree の型付きエージェント —— 群れ |
| メサレドンダ | マルチモデルディベート |
| サンドボックス OS | ブラウザベースのミニ OS、58 アプリ |
| Telegram ブリッジ | スマホから Dulus を実行 |
| MCP サポート | Model Context Protocol |
| ブレインストーム | AI 専門家評議会 |
| SSJ モード | 10 のワークフローショートカットを連鎖 |
| チェックポイント | 任意の会話ターンのスナップショットと巻き戻し |
| コンテキスト圧縮 | 長いセッションを自動圧縮 |
| ローカル OCR | ビジョンモデルトークンなしで画像からテキスト抽出 |
| マルチ言語 | `/lang` コマンド —— 34 ISO コード |
| Composio | 1,000+ SaaS 統合 |
| WebBridge | Playwright によるブラウザ自動化 |

---

## プロバイダ

### 無料（API キー不要）

| プロバイダ | モデル | セットアップ |
|---|---|---|
| **Gemini Guest** | gemini-2.0-flash | ブラウザを開く → "hola" を入力 → 完了 |
| **Claude.ai** | claude-sonnet-4-6 | 既存の claude.ai セッション |
| **Kimi.com** | kimi-k2.5 | 既存の kimi.com セッション |
| **Qwen** | qwen-max, qwen-plus | 既存の qwen.ai セッション |
| **DeepSeek** | deepseek-chat | 既存の deepseek セッション |
| **NVIDIA NIM** | 14 モデル、各 40 RPM | build.nvidia.com で無料登録 |
| **Ollama** | 任意のローカルモデル | `ollama pull qwen2.5-coder` |

### Cloud API（API キー必要）

| プロバイダ | モデル | 環境変数 |
|---|---|---|
| Anthropic | claude-opus-4-6, claude-sonnet-4-6 | `ANTHROPIC_API_KEY` |
| OpenAI | gpt-4o, gpt-4o-mini, o3-mini | `OPENAI_API_KEY` |
| Google | gemini-2.5-pro, gemini-2.0-flash | `GEMINI_API_KEY` |
| DeepSeek | deepseek-chat, deepseek-reasoner | `DEEPSEEK_API_KEY` |
| Qwen | qwen-max, qwen-plus, qwq-32b | `DASHSCOPE_API_KEY` |
| Kimi | moonshot-v1-8k/32k/128k, kimi-k2.5 | `MOONSHOT_API_KEY` |
| LiteLLM | 1 つのゲートウェイ経由 100+ バックエンド | バックエンド固有のキー |

---

## アーキテクチャ

```
ユーザー入力
    |
    v
dulus.py —— REPL、スラッシュコマンド、音声、Telegram、GUI
    |
    ├── agent.py —— マルチターンループ、権限ゲート、ガバナンス
    |       |
    |       ├── providers.py —— マルチプロバイダストリーミング
    |       ├── tool_registry.py —— プラグインシステム
    |       ├── tools.py —— 30+ 内蔵ツール
    |       ├── compaction.py —— コンテキストウィンドウ管理
    |       ├── governance.py —— 予算/権限ガバナンス
    |       └── multi_agent/ —— サブエージェント（群れ）
    |
    ├── context.py —— システムプロンプトビルダー
    |       └── memory/ —— MemPalace セマンティックメモリ
    |
    ├── skill/ —— スキルシステム
    ├── checkpoint/ —— スナップショット + 巻き戻し
    ├── plugin/ —— オートアダプタープラグインシステム
    ├── voice/ —— STT（Whisper）+ TTS（マルチエンジン）
    ├── task/ —— タスク管理
    ├── webbridge/ —— Playwright ブラウザ自動化
    └── dulus_mcp/ —— MCP クライアント
```

---

## 群れ（サブエージェント）

Dulus は**分離された git worktree**で動作する型付きエージェントを生成できます。

```
/agents
Agent(type="coder",    task="refactor auth")
Agent(type="reviewer", task="review #042")
Agent(type="tester",   task="run e2e on auth")
```

---

## パーミッション

| モード | 動作 |
|---|---|
| `auto` *(デフォルト)* | 読み取りは常に許可。書き込み/シェルの前に確認。 |
| `accept-all` | プロンプトなし。すべて自動承認。**YOLO.** |
| `manual` | すべての操作で確認。 |
| `plan` | 読み取り専用。プラン ファイルのみ書き込み可能。 |

---

## スラッシュコマンド

| コマンド | 説明 |
|---|---|
| `/model [名前]` | モデルの表示または切り替え |
| `/memory [クエリ]` | 永続セマンティックメモリ |
| `/voice` | 音声入力（オフライン Whisper） |
| `/brainstorm [トピック]` | ゴースト評議会 |
| `/ssj` | パワーメニュー（10 ショートカット） |
| `/telegram [トークン] [ID]` | Telegram ブリッジ |
| `/checkpoint [ID]` | チェックポイントの一覧/巻き戻し |
| `/plan [説明]` | プラン モードの入/出 |
| `/lang [コード]` | 言語切り替え（34 コード） |
| `/cost` | 消費トークンと USD |
| `/help` | すべてのコマンド |

---

## ライセンス

GPLv3。フォークして、変更して、再配布して —— でもオープンに保ってください。

> *鳥にちなんで命名、ロケットではない。私たちは飛び続ける。*

---

<div align="center">

<p><sub><a href="https://github.com/KevRojo">KevRojo</a> が爪で構築 · サントドミンゴ、ドミニカ共和国 · 2026</sub></p>

</div>
