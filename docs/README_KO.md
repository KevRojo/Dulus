<div align="center">

<img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/dulus-bird.png" alt="Dulus — 팜챗" width="280">

<h1>DULUS</h1>

<h3>당신의 AI 동반자. 챗봇이 아닙니다. 곁을 나는 친구입니다.</h3>

<p>
  <strong>API 키 없이 최첨단 AI를 사용하세요. $0. 신용카드 불필요. 구독 불필요.</strong>
</p>

<p>
  <a href="https://pypi.org/project/dulus/"><img src="https://img.shields.io/pypi/v/dulus.svg?style=flat-square&color=ff6b1f&labelColor=07070a&label=pypi" alt="PyPI"/></a>
  <a href="https://pypi.org/project/dulus/"><img src="https://static.pepy.tech/badge/dulus?style=flat-square" alt="다운로드"/></a>
  <img src="https://img.shields.io/badge/python-3.11+-ff6b1f?style=flat-square&labelColor=07070a" alt="Python"/>
  <img src="https://img.shields.io/badge/라이선스-GPLv3-ff6b1f?style=flat-square&labelColor=07070a" alt="라이선스"/>
  <img src="https://img.shields.io/badge/제공자-100%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="제공자"/>
  <img src="https://img.shields.io/badge/도구-30%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="도구"/>
  <img src="https://img.shields.io/badge/테스트-263%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="테스트"/>
  <a href="https://x.com/KevRojo"><img src="https://img.shields.io/badge/x-%40KevRojo-ff6b1f?style=flat-square&labelColor=07070a&logo=x" alt="X"/></a>
</p>

<p>
  <a href="#kkuiksutateu"><b>퀵 스타트</b></a> ·
  <a href="#gineung"><b>기능</b></a> ·
  <a href="#peurobaideo"><b>제공자</b></a> ·
  <a href="#gujohyung"><b>아키텍처</b></a> ·
</p>

</div>

---

> **팜챗**(*Dulus dominicus*)에서 이름을 따옴 —— 도미니카 공화국의 국조, 자유와 회복력과 함께 나는 상징. Dulus 는 챗봇이 아닙니다. 곁을 나는 동반자, 친구, AI 파트너입니다.

---

## 왜 Dulus 인가?

| | 잠긴 생태계 | 복잡한 프레임워크 | **Dulus** |
|---|---|---|---|
| **설정 시간** | 시간 + 승인 | 며칠의 설정 | **30초** |
| **시작 비용** | $$$ + API 키 | $$$ + 인프라 | **$0** |
| **모델 종속** | 단일 제공자 | 단일 제공자 | **100+ 제공자** |
| **코드베이스** | 블랙박스 | 100K+ 줄 | **~56K 줄의 퍼스트파티 Python** |
| **음성** | 클라우드만 | 미포함 | **오프라인 Whisper** |
| **메모리** | 컨텍스트만 | 수동 | **MemPalace 시맨틱** |

**문제:** 오늘날의 AI 에이전트는 단일 제공자에 잠겨 있거나 설정하려면 ML 공학 박사학위가 필요합니다. 그리고 모두가 시도하기 전에 신용카드를 요구합니다.

**해결책:** Dulus. Python 자율 에이전트로, 어떤 모델에도 연결됩니다 —— 브라우저 세션(Gemini guest, Claude.ai, Kimi, Qwen, DeepSeek)부터 LiteLLM 을 통한 100+ 유료 제공자, 자체 하드웨어의 로컬 모델까지. ~56K 줄의 퍼스트파티 Python. 빌드 단계 없음. 게이트키핑 없음. 발톱만.

---

## 퀵 스타트

### 30초 설치

```bash
pip install dulus && dulus
```

끝입니다. 첫 실행 시 Dulus 는 브라우저를 열고 **Gemini guest 세션**을 캡처합니다(로그인 불필요, API 키 불필요, 신용카드 불필요). 30초 이내에 최첨단 AI 와 채팅할 수 있습니다.

### 원라이너 설치 (권장)

```bash
curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh | bash
```

### Docker (로컬 설정 제로)

```bash
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/.env.example
mv .env.example .env
docker compose up -d
```

---

## 기능

| 기능 | 설명 |
|---|---|
| 멀티 제공자 | 11 네이티브 + LiteLLM 통해 100+ |
| 제로 API 키 | 묶음 브라우저 세션 캡처 |
| 30+ 내장 도구 | 파일, 셸, 웹, OCR, 음성 등 |
| 오토 어댑터 | 모든 Python 리포를 플러그인으로 설치 |
| MemPalace | ChromaDB 기반 시맨틱 메모리 |
| 음성 I/O | Whisper 오프라인 STT. 멀티엔진 TTS |
| 서브 에이전트 | 격리된 git worktree 의 타입 에이전트 —— 무리 |
| 메사 레돈다 | 멀티 모델 토론 |
| 샌드박스 OS | 브라우저 기반 미니 OS, 58 앱 |
| Telegram 브리지 | 스마트폰에서 Dulus 실행 |
| MCP 지원 | Model Context Protocol |
| 브레인스톰 | AI 전문가 위원회 |
| SSJ 모드 | 10 개 워크플로우 바로가기 연결 |
| 체크포인트 | 모든 대화 턴의 스냅샷과 되감기 |
| 컨텍스트 압축 | 긴 세션 자동 압축 |
| 로컬 OCR | 비전 모델 토큰 없이 이미지에서 텍스트 추출 |
| 다국어 | `/lang` 명령 —— 34 ISO 코드 |
| Composio | 1,000+ SaaS 통합 |
| WebBridge | Playwright 브라우저 자동화 |

---

## 제공자

### 묶음 (API 키 불필요)

| 제공자 | 모델 | 설정 |
|---|---|---|
| **Gemini Guest** | gemini-2.0-flash | 브라우저 열기 → "hola" 입력 → 완료 |
| **Claude.ai** | claude-sonnet-4-6 | 기존 claude.ai 세션 |
| **Kimi.com** | kimi-k2.5 | 기존 kimi.com 세션 |
| **Qwen** | qwen-max, qwen-plus | 기존 qwen.ai 세션 |
| **DeepSeek** | deepseek-chat | 기존 deepseek 세션 |
| **NVIDIA NIM** | 14 모델, 각 40 RPM | build.nvidia.com 에서 묶음 등록 |
| **Ollama** | 모든 로컬 모델 | `ollama pull qwen2.5-coder` |

### Cloud API (API 키 필요)

| 제공자 | 모델 | 환경 변수 |
|---|---|---|
| Anthropic | claude-opus-4-6, claude-sonnet-4-6 | `ANTHROPIC_API_KEY` |
| OpenAI | gpt-4o, gpt-4o-mini, o3-mini | `OPENAI_API_KEY` |
| Google | gemini-2.5-pro, gemini-2.0-flash | `GEMINI_API_KEY` |
| DeepSeek | deepseek-chat, deepseek-reasoner | `DEEPSEEK_API_KEY` |
| Qwen | qwen-max, qwen-plus, qwq-32b | `DASHSCOPE_API_KEY` |
| Kimi | moonshot-v1-8k/32k/128k, kimi-k2.5 | `MOONSHOT_API_KEY` |
| LiteLLM | 단일 게이트웨이를 통한 100+ 백엔드 | 백엔드별 키 |

---

## 아키텍처

```
사용자 입력
    |
    v
dulus.py —— REPL, 슬래시 명령, 음성, Telegram, GUI
    |
    ├── agent.py —— 멀티턴 루프, 권한 게이트, 거버넌스
    |       |
    |       ├── providers.py —— 멀티 제공자 스트리밍
    |       ├── tool_registry.py —— 플러그인 시스템
    |       ├── tools.py —— 30+ 내장 도구
    |       ├── compaction.py —— 컨텍스트 윈도우 관리
    |       ├── governance.py —— 예산/권한 거버넌스
    |       └── multi_agent/ —— 서브 에이전트(무리)
    |
    ├── context.py —— 시스템 프롬프트 빌더
    |       └── memory/ —— MemPalace 시맨틱 메모리
    |
    ├── skill/ —— 스킬 시스템
    ├── checkpoint/ —— 스냅샷 + 되감기
    ├── plugin/ —— 오토 어댑터 플러그인 시스템
    ├── voice/ —— STT(Whisper) + TTS(멀티엔진)
    ├── task/ —— 작업 관리
    ├── webbridge/ —— Playwright 브라우저 자동화
    └── dulus_mcp/ —— MCP 클라이언트
```

---

## 무리(서브 에이전트)

Dulus 는**격리된 git worktree**에서 작업하는 타입 에이전트를 생성할 수 있습니다.

```
/agents
Agent(type="coder",    task="refactor auth")
Agent(type="reviewer", task="review #042")
Agent(type="tester",   task="run e2e on auth")
```

---

## 권한

| 모드 | 동작 |
|---|---|
| `auto` *(기본값)* | 읽기는 항상 허용. 쓰기/셸 전에 확인. |
| `accept-all` | 프롬프트 없음. 모두 자동 승인. **YOLO.** |
| `manual` | 모든 작업에서 확인. |
| `plan` | 읽기 전용. 플랜 파일만 쓰기 가능. |

---

## 슬래시 명령

| 명령 | 설명 |
|---|---|
| `/model [이름]` | 모델 표시 또는 전환 |
| `/memory [쿼리]` | 영구 시맨틱 메모리 |
| `/voice` | 음성 입력(오프라인 Whisper) |
| `/brainstorm [주제]` | 고스트 위원회 |
| `/ssj` | 파워 메뉴(10 바로가기) |
| `/telegram [토큰] [ID]` | Telegram 브리지 |
| `/checkpoint [ID]` | 체크포인트 목록/되감기 |
| `/plan [설명]` | 플랜 모드 입/출 |
| `/lang [코드]` | 언어 전환(34 코드) |
| `/cost` | 소비 토큰과 USD |
| `/help` | 모든 명령 |

---

## 라이선스

GPLv3. 포크하고, 수정하고, 재배포하세요 —— 하지만 오픈으로 유지하세요.

> *새 이름, 로켓 아님. 우리는 계속 난다.*

---

<div align="center">

<p><sub><a href="https://github.com/KevRojo">KevRojo</a> 가 발톱으로 구축 · 산토도밍고, 도미니카 공화국 · 2026</sub></p>

</div>
