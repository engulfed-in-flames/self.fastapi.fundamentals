# プロダクションレベルのログ機能設定ガイド：Python編 (1)

## 1. はじめに

本ガイドでは、Python標準のloggingモジュールのみで、プロダクション環境に耐えうるログ機能を構築する方法を説明します。

土台のしっかりしているプロジェクトは、開発から運用に至るすべての工程において無駄な手間を減らしてくれると信じます。その中でも、デバッグや障害の早期検知に直結するログ機能は、スムーズなアプリケーション開発と安定運用に大きく貢献します。

しかし、ログ機能を適切に構築することは、単にログインスタンスをそのまま呼び出すだけで終わるものではありません。基本設定のままでは、開発環境で正常に動いているように見えても、本番環境でのユーザー数の増加やネットワークの遅延に伴い、何気ないログ出力処理がシステム全体の深刻なボトルネックに発展する可能性があります。

ログはアプリケーションの運用・監視・分析に欠かせない重要な情報ですが、ログ出力のせいでメインのビジネスロジックが阻害されたり、アプリケーションの処理が止まったりすることは絶対に避けるべきです。

プロダクション環境に求められるログ機能の主な要件は以下の通りです：

1. ノンブロッキング（Non-blocking）：ログの入出力(I/O)の完了を待たずに、メインのプログラム処理を即座に再開。
2. 自由なカスタマイズ：アプリケーション内の各モジュールの目的に応じて、ログの出力先やフォーマットを柔軟に設定。
3. 視認性の高いフォーマット：プレーンテキストではなく、構造化され、人間にもログ監視ツール（またはAI）にも解析しやすいJSONやJSONLフォーマットの採用

現在、私たちのDISプロジェクトのログは、ブロッキング方式であり、カスタマイズが難しく、プレーンテキスト形式のまま出力されています。コンプライアンス遵守の観点から設定変更を制限する意図は理解できますが、現在のブロッキング方式では、ログを出力するたびにメインスレッドが標準出力の完了を待機してしまい、高トラフィック時にボトルネックの起因としてスーループット低下に繋がります。また、プレーンテキスト形式のログは、人間の目線で見にくいかつ、DatadogやCloudWatchなどの監視ツールによる解析を困難さすます。

さらに最近は、インフラ環境に監視用のAIを導入してログを自動分析させる運用が主流になりつつあります。ここでAIの活用コストは読み込ませるデータの構造に直結します。AIに解析しづらい不整形なログを処理させることは、トークン数の無駄遣いによるコスト増大を招くだけでなく、コンテキストの誤認による分析精度の低下にも繋がります。そのため、ログをJSONLのような一貫性のある構造化フォーマットに統一することは、システムのパフォーマンス向上だけでなく、運用コストの最適化や将来的なAI運用の自動化おいても不可欠です。

上記の問題認識に基づき、本ガイドを通じて達成したいゴールは以下となります。

### 目指すゴール

* **Python標準Loggerの仕組みを理解**: Logger, Handler, Formatter, Filterの役割分担の明確化。
* **ログ出力形式の構造化（JSON）**: すべてのログをキー・バリュー形式のJSONで出力。
* **ログ出力のノンブロッキング化**: `QueueHandler`と`QueueListener`を活用し、ログ出力を非同期で処理。
* **コーディング実力の向上**: 本ガイドを通じてPythonのベストプラクティスを体得

---

## 2. Python標準Loggerの仕組み

Pythonの`logging`モジュールは、主に以下の4つのコンポーネントで構成されています。これらを制御することから柔軟なログ設定ができます。

```txt
[アプリケーション]
│
▼
1. Logger (ログの入り口)
│
▼
2. Filter (ログレコードの選別・改変)
│
▼
3. Handler (出力先の決定: stdout/stderr/file/queue)
│
▼
4. Formatter (ログの整形)
│
▼
[ログ出力先 (コンソール/ファイル等)]
```

1. **Logger**: アプリケーションコードが直接呼び出すインターフェース。ログレベル（DEBUG, INFO, etc.）に基づき、処理内容を判定。
2. **Filter**: より詳細な条件でログレコード（`LogRecord`）をフィルタリング、または動的にコンテキスト情報を追加・改変。
3. **Handler**: ログの「出力先」を制御。標準出力（`StreamHandler`）、ファイル（`RotatingFileHandler`）、そして非同期化のためのメモリキュー（`QueueHandler`）など。
4. **Formatter**: `LogRecord`オブジェクトを、最終的な出力形式（文字列やJSONなど）に変換。

---

## 3. `BasicConfig`：基本設定

本論に入る前に、まずはPythonのロガーを実際に動かしてみましょう。
Pythonのロギングは、標準ライブラリのloggingモジュールを呼び出すだけで、外部ライブラリを一切使わずに利用できます。

ロガーは、出力先やフォーマット、出力するログレベルの閾値など、さまざまな設定ができます。ここでは、まずロギングの基本動作を理解するために、一番シンプルな設定方法から触れていきます。

具体的には、loggingモジュールの`basicConfig`を使用して最小限の設定だけを行い、いくつかのログを出力して結果を確認します。
まず、`logger.py`というファイルを作成し、以下のソースコードをコピペしてください。


```py
import logging

logging.basicConfig(
    filename="logs/logs.txt",  # 出力先のファイルパス
    level=logging.info,  # 出力するログレベルの閾値を設定
    format="[%(asctime)s] %(levelname)s: %(message)s",  # ろぐのフォーマット
    datefmt="%Y-%m-%d %H:%M:%S",  # 日時のフォーマット
)
logger = logging.getLogger()  # ログインスタンスの取得

logger.debug("DEBUGログです。")  # DEBUGレベルのログを出力
logger.info("INFOログです。")  # INFOレベルのログを出力
logger.warning("WARNINGログです。")  # WARNINGレベルのログを出力
logger.error("ERRORログです。")  # ERRORレベルのログを出力
logger.critical("CRITICALログです。")  # CRITICALレベルのログを出力

try:
    1 / 0
except ZeroDivisionError as e:
    logger.exception("割り算がまちがっています。")
```
コピペが完了したら、実行してみましょう。（本ガイドでは、`uv`というPythonツールを利用してプログラムを実行します。）

```bash
# 実行例
uv run logger.py
```

実行しましたら、`logs/logs.txt`の中身を確認してみましょう。以下のようなログが記録されているはずです。

(出力されたログを確認)

いかがでしょうか。

わずか数行の基本設定だけでも、日時やログレベル、さらにエラーの詳細ース（スタックトレース）まで、かなり分かりやすいログが出力されたことが確認できます。最後のスタックトレースは少し長く感じられるかもしれませんが、まだ許容範囲内だと思います。

しかし、実際のアプリケーション運用において、このような単発のログだけで終わることはありません。システムが稼働すれば、大量のリクエストやエラーが連続します。

今度は、ログ出力部分を以下のように書き換え、`ZeroDivisionError`と`ValueError`をそれぞれ10回ずつ繰り返して実行してみましょう。

```py
# ...（先と同様）
logger.error("ERRORログです。")
logger.critical("CRITICALログです。")

for i in range(10):
    try:
        1 / 0
    except ZeroDivisionError as e:
        logger.exception("割り算が正しくありません。")

    try:
        dt.datetime.strptime("123", "%y-%m-%d %H:%M:%S")
    except ValueError as e:
        logger.exception("日時形式が正しくありません。")
```

この状態で、再度コマンドを実行します。

```bash
uv run logger.py
```

出力されたログをもう一度確認してみましょう。

(出力されたログを確認)

いかがでしょうか。

先ほどとは一転して、ログが延々と垂直に積み重なり、著しく視認性が低下したことを体感できるはずです。実は、これほど大量に吐き出されたログでさえ、実際のプロダクション環境（実世界のログ）に比べたらわずかに過ぎません。

このような「生のテキストログ」をそのまま本番環境で運用すると、以下のような致命的な問題が発生します。

- ログが大量に積み重なるため、どこで本当の致命的なバグが起きているか見つけ出すのが極めて困難。
- 各ログがどのような因果関係で繋がっているか追跡するのが極めて困難。
- 複数スレッドや非同期処理のログが混ざり合うと、コンテキストの判別が極めて困難。

もしかしたら、障害が発生するたびにこの生のテキストログをそのまま生成AIに丸ごと貼り付けて解決を試みてはないでしょうか。

もちろんそれも一つの手段ではありますが、少しの手間でログの構成やフォーマットをはじめから見直しておけば、人間にとっても、そして監視ツールや生成AIにとっても、一瞬で異常を検知・分析できる形に変えることができます。

次の章では、この視認性と劇的に向上させるための「Formatter」を設定してみます。

---

# プロダクションレベルのログ機能設定ガイド：Python編 (2)

---

## 4. `Formatter`：ログの整形

### ステップ 2: フォーマッターの作成 (`/logger/formatters.py`)

最近、運用・監視の自動化のため、ログをAIに読み込ませ、エラーの自動検出、膨大なデータの要約、傾向の分析などを瞬時に行えることが期待されています。この時に生のログよりはJSON形式に読み込ませると、AIにログの意味を正確に理解させることができます。

さっさと、「Formatter」を作成してみましょう。

```python
import json
import logging
import datetime as dt
from typing import override

class JSONFormatter(logging.Formatter):
    """
    LogRecordをJSON文字列に変換するプロダクション仕様のフォーマッター
    """

    def __init__(self, **kwargs):
        super().__init__()
        # 共通で含めたい静的メタデータがあればここで定義
        self.default_kwargs = kwargs

    def format(self, record: logging.LogRecord) -> str:
        # 基本的なログ情報の抽出
        log_data = {
            "timestamp": dt.datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
            "process": record.processName,
            "thread": record.threadName
        }

        # 例外情報が含まれている場合の処理
        if record.exc_info:
            log_data["exc_info"] = self.formatException(record.exc_info)

        # スタックトレース情報が含まれている場合の処理
        if record.stack_info:
            log_data["stack_info"] = self.formatStack(record.stack_info)

        # 共通メタデータをマージ
        log_data.update(self.default_kwargs)

        # JSON文字列に変換
        # ASCIIでない文字（日本語）をそのまま保存するため、`ensure_ascii=False`を指定
        return json.dumps(log_data, ensure_ascii=False)
```

### ステップ 1: フィルターの作成 (`/logger/filters.py`)
ログの選別や、機密情報（パスワードやトークンなど）のマスク処理、あるいはFastAPIのヘルスチェックログ（`/healthz`）の除外などを行うカスタムフィルターを作成します。

```python
import logging

class SensitiveDataFilter(logging.Filter):
    """
    ログメッセージ内の機密情報をマスクする、または特定のログを除外するフィルター
    """
    def __init__(self, pattern_to_mask: str = "password"):
        super().__init__()
        self.pattern_to_mask = pattern_to_mask

    def filter(self, record: logging.LogRecord) -> bool:
        # 1. 特定の不要なエンドポイント（例: ヘルスチェック）のログを除外
        if hasattr(record, "args") and isinstance(record.args, tuple):
            for arg in record.args:
                if isinstance(arg, str) and "/healthz" in arg:
                    return False

        # 2. メッセージ内の機密情報の簡易マスク処理
        if isinstance(record.msg, str) and self.pattern_to_mask in record.msg:
            record.msg = record.msg.replace(self.pattern_to_mask, "********")

        return True

```
### ステップ 3: ハンドラーと非同期（ノンブロッキング）化の設定 (`/logger/handlers.py`)

FastAPIのパフォーマンスを阻害しないよう、メインスレッドのログ出力をメモリ上のキュー(`queue.Queue`)に書き込むだけに留め、実際のI/O処理（標準出力・ファイル書き込み）は別スレッドの`QueueListener`に処理させます。

```python
import logging
import queue
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
import sys

def create_async_logging_setup(
    stdout_formatter: logging.Formatter,
    file_formatter: logging.Formatter,
    log_filter: logging.Filter,
    file_path: str = "app.log"
) -> QueueHandler:
    """
    QueueHandlerとQueueListenerを構築し、バックグラウンドで同期ログを実行する。
    FastAPIのメインスレッドをブロックしないための非同期ロギング基盤。
    """
    # 1. 実際のログI/Oを担当する同期ハンドラーの作成
    # 標準出力 (INFO以上)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(stdout_formatter)
    stdout_handler.addFilter(log_filter)

    # 標準エラー出力 (ERROR以上)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(stdout_formatter)

    # ローカルファイル出力 (ログローテーション付き)
    file_handler = RotatingFileHandler(
        file_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    file_handler.addFilter(log_filter)

    # 2. ログレコードを媒介するインメモリキューの作成
    log_queue = queue.Queue(-1)  # スロット数無制限

    # 3. メインスレッドが書き込むための QueueHandler
    async_handler = QueueHandler(log_queue)

    # 4. バックグラウンドでキューからレコードを取り出して各同期ハンドラーに配る Listener
    # ※ この listener オブジェクトはアプリケーション終了時まで保持・管理する必要があります
    listener = QueueListener(
        log_queue, stdout_handler, stderr_handler, file_handler, respect_handler_level=True
    )

    # リスナーの起動
    listener.start()

    # アプリケーションから参照できるようにグローバルオブジェクトとして保持するか、
    # 終了処理（stop）のために listener をハンドラーにラップして返す
    async_handler.listener = listener  # カスタム属性として参照保持

    return async_handler

```

### ステップ 4: 高レベル集中管理設定 (`/logger/config.py`)

作成したコンポーネントを、高レベルな設定マネージャーとして1つに統合します。Pythonでは通常 `dictConfig` を利用して一括定義しますが、非同期の `QueueListener` のライフサイクル制御を含めて関数化します。

```python
import logging
import logging.config
from logger.formatters import JSONFormatter
from logger.filters import SensitiveDataFilter
from logger.handlers import create_async_logging_setup

_global_listener_handler = None

def configure_production_logging():
    """
    アプリケーション全体のロギングシステムを一括初期化する
    """
    global _global_listener_handler

    # 1. フォーマッターとフィルターのインスタンス化
    json_formatter = JSONFormatter(environment="production", service_name="fastapi-app")
    sensitive_filter = SensitiveDataFilter()

    # 2. 非同期ハンドラー設定の構築
    async_handler = create_async_logging_setup(
        stdout_formatter=json_formatter,
        file_formatter=json_formatter,
        log_filter=sensitive_filter,
        file_path="production_app.json.log"
    )

    # 3. ルートロガーの取得と設定
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 最低ラインはDEBUGを通し、ハンドラー側で絞る

    # 既存のデフォルトハンドラーをクリア
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # ルートロガーに非同期ハンドラーを1つだけ登録
    root_logger.addHandler(async_handler)

    # Uvicornのアクセスロガーなど、他のライブラリのログもルートへ伝播（Propagate）させる
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        sub_logger = logging.getLogger(logger_name)
        sub_logger.handlers = []  # Uvicornの標準ハンドラーを削除
        sub_logger.propagate = True

    # 終了処理のためにグローバルに保持
    _global_listener_handler = async_handler

def shutdown_production_logging():
    """
    アプリケーション終了時にキューに残ったログをフラッシュし、スレッドを安全に停止する
    """
    global _global_listener_handler
    if _global_listener_handler and hasattr(_global_listener_handler, "listener"):
        _global_listener_handler.listener.stop()

```

---

## 4. FastAPI への高レベル統合 (`/app/main.py`)

最後に、構築したロギング基盤を FastAPI アプリケーションに組み込みます。FastAPI の `lifespan` イベント（Startup / Shutdown）を利用することで、アプリケーションの起動時にロガーを非同期化し、終了時に安全にバックグラウンドスレッドを停止（シャットダウン）させます。

```python
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
import logging
import time

# 作成したロギング設定のインポート
from logger.config import configure_production_logging, shutdown_production_logging

logger = logging.getLogger("app.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 【Startup】プロダクション向け非同期・JSONロガーの初期化
    configure_production_logging()
    logger.info("Application startup: Asynchronous JSON logging initialized.")

    yield

    # 【Shutdown】バックグラウンドスレッド(QueueListener)の安全な停止
    logger.info("Application shutdown: Stopping logging listener.")
    shutdown_production_logging()

app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    """
    すべてのHTTPリクエストを構造化JSONとして自動記録するミドルウェア
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    # extra引数に辞書を渡すことで、JSONのトップレベルにカスタムフィールドを展開可能
    logger.info(
        f"HTTP {request.method} {request.url.path} completed",
        extra={
            "http_method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time_ms": round(process_time * 1000, 2),
            "client_host": request.client.host if request.client else None
        }
    )
    return response

@app.get("/")
async def read_root():
    logger.debug("Debug event in root endpoint")
    return {"status": "ok"}

@app.get("/healthz")
async def health_check():
    # SensitiveDataFilterによって、このエンドポイントのログは自動的に除外されます
    logger.info("Checking system health...")
    return {"status": "healthy"}

@app.get("/admin/login")
async def admin_login():
    # SensitiveDataFilterによって、"password"文字列が「********」に自動マスクされます
    logger.warning("Failed login attempt with password=my_secret_password_123")
    return {"status": "unauthorized"}

```

---

## 5. 運用のポイント

1. **パフォーマンスの極大化**: `QueueHandler` を介しているため、エンドポイント内で `logger.info()` などの重いI/Oを伴うメソッドを呼んでも、FastAPIのイベントループ（メインスレッド）は一切ブロックされません。コンソールやファイルへの物理的な書き込みは、裏側の `QueueListener` スレッドが完全に非同期で処理します。
2. **コンテキスト情報の集約**: ミドルウェア等で `extra` 引数を活用してリクエストIDやユーザーIDを付与することで、分散トレーシングが容易になります。
3. **ログのローテーション**: `/logger/handlers.py` で `RotatingFileHandler` を採用しているため、ディスク溢れを防ぎつつ安全にファイルログを管理できます。
"""

with open("GEMINI.md", "w", encoding="utf-8") as f:
f.write(markdown_content)
print("GEMINI.md has been written successfully.")

```
```python?code_reference&code_event_index=6
markdown_content = """# FastAPIプロダクション環境向け Python Logger 設定完全ガイド

本書は、FastAPIアプリケーションにおいて、プロダクション環境に耐えうる「構造化（JSON）」「非同期（ノンブロッキング）」「階層的管理」を満たしたロギングシステムを、Python標準の`logging`モジュールのみ（外部ライブラリ不使用）で構築するためのステップ・バイ・ステップガイドです。

## 1. 現状の課題とアーキテクチャの概要

### 現状の課題
1. **同期・ブロッキング処理**: 標準のファイル出力や標準出力は同期処理（I/Oブロック）であるため、高トラフィックなFastAPIのイベントループをブロッキングし、スループットを著しく低下させます。
2. **プレーンテキスト形式**: ログが単なる文字列として出力されているため、CloudWatch、Datadog、ELKなどのログ監視・分析ツールでの検索や集計（パース）が困難です。

### 目指すゴール
* **Loggerの解剖学（Anatomy）の理解**: Logger, Handler, Formatter, Filter の役割分担の明確化。
* **構造化（JSON）ロギング**: すべてのログをキー・バリュー形式のJSONで出力。
* **ノンブロッキング（非同期）化**: `QueueHandler`と`QueueListener`を活用し、ログI/Oを別スレッドに移譲。
* **高レベルな一元管理**: `/logger/config.py`における`dictConfig`による集中制御。

---

## 2. Python Logger の内部構造（Anatomy）

Pythonの`logging`モジュールは、主に以下の4つのコンポーネントで構成されています。これらが連動することで、柔軟なログ制御が可能になります。


```

```text
File successfully created.


```

[アプリケーション]
│
▼

1. Logger (ログの入り口: 閾値チェック)
│
▼
2. Filter (ログレコードの選別・改変)
│
▼
3. Handler (出力先の決定: stdout/stderr/file/queue)
│
▼
4. Formatter (出力フォーマットの整形: JSON化)
│
▼
[ログ出力先 (コンソール/ファイル等)]

```

1. **Logger (ロガー)**: アプリケーションコードが直接呼び出すインターフェースです。ログレベル（DEBUG, INFO, etc.）に基づき、処理を進めるか否かを判定します。
2. **Filter (フィルター)**: ログレベルよりも詳細な条件でログレコード（`LogRecord`）をフィルタリングしたり、動的にコンテキスト情報を追加・改変したりします。
3. **Handler (ハンドラー)**: ログの「出力先」を制御します。標準出力（`StreamHandler`）、ファイル（`RotatingFileHandler`）、そして非同期化のためのメモリキュー（`QueueHandler`）などがあります。
4. **Formatter (フォーマッター)**: `LogRecord`オブジェクトを、最終的な出力形式（文字列やJSONなど）に変換します。

---

## 3. プロダクション向け実装ステップ

設計に従い、コードを `/logger` ディレクトリ内に分割して実装します。

### ステップ 1: フィルターの作成 (`/logger/filters.py`)
ログの選別や、機密情報（パスワードやトークンなど）のマスク処理、あるいはFastAPIのヘルスチェックログ（`/healthz`）の除外などを行うカスタムフィルターを作成します。

```python
import logging

class SensitiveDataFilter(logging.Filter):
    \"\"\"
    ログメッセージ内の機密情報をマスクする、または特定のログを除外するフィルター
    \"\"\"
    def __init__(self, pattern_to_mask: str = "password"):
        super().__init__()
        self.pattern_to_mask = pattern_to_mask

    def filter(self, record: logging.LogRecord) -> bool:
        # 1. 特定の不要なエンドポイント（例: ヘルスチェック）のログを除外
        if hasattr(record, "args") and isinstance(record.args, tuple):
            for arg in record.args:
                if isinstance(arg, str) and "/healthz" in arg:
                    return False

        # 2. メッセージ内の機密情報の簡易マスク処理
        if isinstance(record.msg, str) and self.pattern_to_mask in record.msg:
            record.msg = record.msg.replace(self.pattern_to_mask, "********")

        return True

```

### ステップ 2: フォーマッターの作成 (`/logger/formatters.py`)

標準のテキスト出力から、集計・分析が容易なJSON形式へ変換するカスタムフォーマッターを実装します。外部ライブラリに依存せず、標準の`json`モジュールを使用します。

```python
import json
import logging
import datetime

class JSONFormatter(logging.Formatter):
    \"\"\"
    LogRecordをJSON文字列に変換するプロダクション仕様のフォーマッター
    \"\"\"
    def __init__(self, **kwargs):
        super().__init__()
        # 共通で含めたい静的メタデータがあればここで定義
        self.default_kwargs = kwargs

    def format(self, record: logging.LogRecord) -> str:
        # 基本的なログ情報の抽出
        log_data = {
            "timestamp": datetime.datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func_name": record.funcName,
            "line_no": record.lineno
        }

        # 例外情報 (Exception) が含まれる場合の処理
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # extra={} で渡された動的カスタム属性の取り込み
        # loggingの予約語と衝突しないもののみを追加
        reserved_attrs = {
            "args", "asctime", "created", "exc_info", "exc_text", "filename",
            "funcName", "levelname", "levelno", "lineno", "module", "msecs",
            "msg", "name", "pathname", "process", "processName", "relativeCreated",
            "stack_info", "thread", "threadName"
        }
        for key, value in record.__dict__.items():
            if key not in reserved_attrs:
                log_data[key] = value

        # 静的メタデータのマージ
        log_data.update(self.default_kwargs)

        return json.dumps(log_data, ensure_ascii=False)

```

### ステップ 3: ハンドラーと非同期（ノンブロッキング）化の設定 (`/logger/handlers.py`)

FastAPIのパフォーマンスを阻害しないよう、メインスレッドのログ出力をメモリ上のキュー(`queue.Queue`)に書き込むだけに留め、実際のI/O処理（標準出力・ファイル書き込み）は別スレッドの`QueueListener`に処理させます。

```python
import logging
import queue
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
import sys

def create_async_logging_setup(
    stdout_formatter: logging.Formatter,
    file_formatter: logging.Formatter,
    log_filter: logging.Filter,
    file_path: str = "app.log"
) -> QueueHandler:
    \"\"\"
    QueueHandlerとQueueListenerを構築し、バックグラウンドで同期ログを実行する。
    FastAPIのメインスレッドをブロックしないための非同期ロギング基盤。
    \"\"\"
    # 1. 実際のログI/Oを担当する同期ハンドラーの作成
    # 標準出力 (INFO以上)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(stdout_formatter)
    stdout_handler.addFilter(log_filter)

    # 標準エラー出力 (ERROR以上)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(stdout_formatter)

    # ローカルファイル出力 (ログローテーション付き)
    file_handler = RotatingFileHandler(
        file_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    file_handler.addFilter(log_filter)

    # 2. ログレコードを媒介するインメモリキューの作成
    log_queue = queue.Queue(-1)  # スロット数無制限

    # 3. メインスレッドが書き込むための QueueHandler
    async_handler = QueueHandler(log_queue)

    # 4. バックグラウンドでキューからレコードを取り出して各同期ハンドラーに配る Listener
    # ※ この listener オブジェクトはアプリケーション終了時まで保持・管理する必要があります
    listener = QueueListener(
        log_queue, stdout_handler, stderr_handler, file_handler, respect_handler_level=True
    )

    # リスナーの起動
    listener.start()

    # アプリケーションから参照できるようにグローバルオブジェクトとして保持するか、
    # 終了処理（stop）のために listener をハンドラーにラップして返す
    async_handler.listener = listener  # カスタム属性として参照保持

    return async_handler

```

### ステップ 4: 高レベル集中管理設定 (`/logger/config.py`)

作成したコンポーネントを、高レベルな設定マネージャーとして1つに統合します。Pythonでは通常 `dictConfig` を利用して一括定義しますが、非同期の `QueueListener` のライフサイクル制御を含めて関数化します。

```python
import logging
import logging.config
from logger.formatters import JSONFormatter
from logger.filters import SensitiveDataFilter
from logger.handlers import create_async_logging_setup

_global_listener_handler = None

def configure_production_logging():
    \"\"\"
    アプリケーション全体のロギングシステムを一括初期化する
    \"\"\"
    global _global_listener_handler

    # 1. フォーマッターとフィルターのインスタンス化
    json_formatter = JSONFormatter(environment="production", service_name="fastapi-app")
    sensitive_filter = SensitiveDataFilter()

    # 2. 非同期ハンドラー設定の構築
    async_handler = create_async_logging_setup(
        stdout_formatter=json_formatter,
        file_formatter=json_formatter,
        log_filter=sensitive_filter,
        file_path="production_app.json.log"
    )

    # 3. ルートロガーの取得と設定
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 最低ラインはDEBUGを通し、ハンドラー側で絞る

    # 既存のデフォルトハンドラーをクリア
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # ルートロガーに非同期ハンドラーを1つだけ登録
    root_logger.addHandler(async_handler)

    # Uvicornのアクセスロガーなど、他のライブラリのログもルートへ伝播（Propagate）させる
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        sub_logger = logging.getLogger(logger_name)
        sub_logger.handlers = []  # Uvicornの標準ハンドラーを削除
        sub_logger.propagate = True

    # 終了処理のためにグローバルに保持
    _global_listener_handler = async_handler

def shutdown_production_logging():
    \"\"\"
    アプリケーション終了時にキューに残ったログをフラッシュし、スレッドを安全に停止する
    \"\"\"
    global _global_listener_handler
    if _global_listener_handler and hasattr(_global_listener_handler, "listener"):
        _global_listener_handler.listener.stop()

```

---

## 4. FastAPI への高レベル統合 (`/app/main.py`)

最後に、構築したロギング基盤を FastAPI アプリケーションに組み込みます。FastAPI の `lifespan` イベント（Startup / Shutdown）を利用することで、アプリケーションの起動時にロガーを非同期化し、終了時に安全にバックグラウンドスレッドを停止（シャットダウン）させます。

```python
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
import logging
import time

# 作成したロギング設定のインポート
from logger.config import configure_production_logging, shutdown_production_logging

logger = logging.getLogger("app.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 【Startup】プロダクション向け非同期・JSONロガーの初期化
    configure_production_logging()
    logger.info("Application startup: Asynchronous JSON logging initialized.")

    yield

    # 【Shutdown】バックグラウンドスレッド(QueueListener)の安全な停止
    logger.info("Application shutdown: Stopping logging listener.")
    shutdown_production_logging()

app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    \"\"\"
    すべてのHTTPリクエストを構造化JSONとして自動記録するミドルウェア
    \"\"\"
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    # extra引数に辞書を渡すことで、JSONのトップレベルにカスタムフィールドを展開可能
    logger.info(
        f"HTTP {request.method} {request.url.path} completed",
        extra={
            "http_method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time_ms": round(process_time * 1000, 2),
            "client_host": request.client.host if request.client else None
        }
    )
    return response

@app.get("/")
async def read_root():
    logger.debug("Debug event in root endpoint")
    return {"status": "ok"}

@app.get("/healthz")
async def health_check():
    # SensitiveDataFilterによって、このエンドポイントのログは自動的に除外されます
    logger.info("Checking system health...")
    return {"status": "healthy"}

@app.get("/admin/login")
async def admin_login():
    # SensitiveDataFilterによって、"password"文字列が「********」に自動マスクされます
    logger.warning("Failed login attempt with password=my_secret_password_123")
    return {"status": "unauthorized"}

```

---

## 5. 運用のポイント

1. **パフォーマンスの極大化**: `QueueHandler` を介しているため、エンドポイント内で `logger.info()` などの重いI/Oを伴うメソッドを呼んでも、FastAPIのイベントループ（メインスレッド）は一切ブロックされません。コンソールやファイルへの物理的な書き込みは、裏側の `QueueListener` スレッドが完全に非同期で処理します。
2. **コンテキスト情報の集約**: ミドルウェア等で `extra` 引数を活用してリクエストIDやユーザーIDを付与することで、分散トレーシングが容易になります。
3. **ログのローテーション**: `/logger/handlers.py` で `RotatingFileHandler` を採用しているため、ディスク溢れを防ぎつつ安全にファイルログを管理できます。
"""

with open("GEMINI.md", "w", encoding="utf-8") as f:
f.write(markdown_content)
print("File successfully created.")

```
Your Markdown (.md) file is ready
[file-tag: code-generated-file-0-1779498011784003825]

```
