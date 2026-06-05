<div align="center">

<img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/dulus-bird.png" alt="Dulus — طائر النخيل" width="280">

<h1>DULUS</h1>

<h3>رفيقك الذكي. ليس روبوت دردشة. صديق يطير بجانبك.</h3>

<p>
  <strong>استخدم الذكاء الاصطناعي المتقدم بدون مفتاح API. $0. بدون بطاقة. بدون اشتراك.</strong>
</p>

<p>
  <a href="https://pypi.org/project/dulus/"><img src="https://img.shields.io/pypi/v/dulus.svg?style=flat-square&color=ff6b1f&labelColor=07070a&label=pypi" alt="PyPI"/></a>
  <a href="https://pypi.org/project/dulus/"><img src="https://static.pepy.tech/badge/dulus?style=flat-square" alt="التنزيلات"/></a>
  <img src="https://img.shields.io/badge/python-3.11+-ff6b1f?style=flat-square&labelColor=07070a" alt="Python"/>
  <img src="https://img.shields.io/badge/الترخيص-GPLv3-ff6b1f?style=flat-square&labelColor=07070a" alt="الترخيص"/>
  <img src="https://img.shields.io/badge/مزودو-100%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="المزودون"/>
  <img src="https://img.shields.io/badge/أدوات-30%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="الأدوات"/>
  <img src="https://img.shields.io/badge/اختبارات-263%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="الاختبارات"/>
  <a href="https://x.com/KevRojo"><img src="https://img.shields.io/badge/x-%40KevRojo-ff6b1f?style=flat-square&labelColor=07070a&logo=x" alt="X"/></a>
</p>

<p>
  <a href="#البداية-السريعة"><b>البداية السريعة</b></a> ·
  <a href="#الميزات"><b>الميزات</b></a> ·
  <a href="#المزودون"><b>المزودون</b></a> ·
  <a href="#البنية-التحتية"><b>البنية التحتية</b></a> ·
  <a href="#التوكن"><b>$DULUS</b></a>
</p>

</div>

---

> سُمّي على شرف **طائر النخيل** (*Dulus dominicus*)، الطائر الوطني لجمهورية الدومينيكان — رمز الحرية والمرونة والطيران معاً. Dulus ليس روبوت دردشة. إنه رفيقك، صديقك، شريكك الذكي الذي يطير بجانبك.

---

## لماذا Dulus؟

| | الأنظمة البيئية المغلقة | الإطارات المعقدة | **Dulus** |
|---|---|---|---|
| **وقت الإعداد** | ساعات + موافقات | أيام من التكوين | **30 ثانية** |
| **التكلفة الأولية** | $$$ + مفاتيح API | $$$ + بنية تحتية | **$0** |
| **قفل المزود** | مزود واحد | مزود واحد | **100+ مزود** |
| **قاعدة الكود** | صندوق أسود | 100K+ سطر | **~12K سطر مقروء** |
| **الصوت** | السحابة فقط | غير مضمن | **Whisper بدون اتصال** |
| **الذاكرة** | السياق فقط | يدوي | **MemPalace الدلالي** |

**المشكلة:** وكلاء الذكاء الاصطناعي اليوم إما مقفلون على مزود واحد أو يتطلبون دكتوراه في هندسة ML للتكوين. وجميعهم يريدون بطاقتك الائتمانية قبل أن تتمكن من تجربتهم.

**الحل:** Dulus. وكيل Python مستقل يتصل بأي نموذج — من جلسات المتصفح المجانية إلى 100+ مزود مدفوع عبر LiteLLM، إلى النماذج المحلية على Mac M2 الخاص بك. ~12K سطر Python مقروء. بدون خطوة بناء. بدون قيود.

---

## البداية السريعة

### التثبيت في 30 ثانية

```bash
pip install dulus && dulus
```

هذا كل شيء. في التشغيل الأول، يفتح Dulus المتصفح، ويلتقط **جلسة ضيف Gemini** (بدون تسجيل دخول، بدون مفتاح API، بدون بطاقة)، وتدردش مع الذكاء الاصطناعي المتقدم في أقل من 30 ثانية.

### المثبت One-liner (موصى به)

```bash
curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh | bash
```

### Docker (بدون إعداد محلي)

```bash
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/.env.example
mv .env.example .env
docker compose up -d
```

---

## الميزات

| الميزة | الوصف |
|---|---|
| متعدد المزودين | 11 أصلي + 100+ عبر LiteLLM |
| صفر مفتاح API | التقاط جلسات المتصفح المجانية |
| 30+ أداة مدمجة | ملفات، shell، ويب، OCR، صوت، وأكثر |
| المحول التلقائي | تثبيت أي مستودع Python كملحق |
| MemPalace | ذاكرة دلالية مع ChromaDB |
| صوت I/O | STT بدون اتصال عبر Whisper. TTS متعدد المحركات |
| الوكلاء الفرعيون | وكلاء مكتوبون في git worktrees معزولة —— القطيع |
| المائدة المستديرة | نقاش متعدد النماذج |
| نظام Sandbox OS | نظام تشغيل مصغر قائم على المتصفح مع 58 تطبيقاً |
| جسر Telegram | تشغيل Dulus من هاتفك |
| دعم MCP | بروتوكول سياق النموذج |
| العصف الذهني | مجلس خبراء الذكاء الاصطناعي |
| وضع SSJ | 10 اختصارات سير عمل متسلسلة |
| نقاط التفتيش | لقطة وإرجاع أي دورة محادثة |
| ضغط السياق | ضغط الجلسات الطويلة تلقائياً |
| OCR محلي | استخراج النص من الصور بدون رموز نموذج الرؤية |
| متعدد اللغات | أمر `/lang` — 34 رمز ISO |
| Composio | 1,000+ تكامل SaaS |
| WebBridge | أتمتة المتصفح عبر Playwright |

---

## المزودون

### مجاني (بدون مفتاح API)

| المزود | النماذج | الإعداد |
|---|---|---|
| **Gemini Guest** | gemini-2.0-flash | افتح المتصفح → اكتب "مرحباً" → تم |
| **Claude.ai** | claude-sonnet-4-6 | جلستك الحالية على claude.ai |
| **Kimi.com** | kimi-k2.5 | جلستك الحالية على kimi.com |
| **Qwen** | qwen-max, qwen-plus | جلستك الحالية على qwen.ai |
| **DeepSeek** | deepseek-chat | جلستك الحالية على deepseek |
| **NVIDIA NIM** | 14 نموذجاً، 40 RPM لكل منها | تسجيل مجاني على build.nvidia.com |
| **Ollama** | أي نموذج محلي | `ollama pull qwen2.5-coder` |

### Cloud API (يتطلب مفتاح API)

| المزود | النماذج | متغير البيئة |
|---|---|---|
| Anthropic | claude-opus-4-6, claude-sonnet-4-6 | `ANTHROPIC_API_KEY` |
| OpenAI | gpt-4o, gpt-4o-mini, o3-mini | `OPENAI_API_KEY` |
| Google | gemini-2.5-pro, gemini-2.0-flash | `GEMINI_API_KEY` |
| DeepSeek | deepseek-chat, deepseek-reasoner | `DEEPSEEK_API_KEY` |
| Qwen | qwen-max, qwen-plus, qwq-32b | `DASHSCOPE_API_KEY` |
| Kimi | moonshot-v1-8k/32k/128k, kimi-k2.5 | `MOONSHOT_API_KEY` |
| LiteLLM | 100+ باطن عبر بوابة واحدة | مفتاح الباطن المحدد |

---

## البنية التحتية

```
إدخال المستخدم
    |
    v
dulus.py —— REPL، أوامر slash، صوت، Telegram، GUI
    |
    ├── agent.py —— حلقة متعددة الأدوار، بوابات الأذونات، الحوكمة
    |       |
    |       ├── providers.py —— بث متعدد المزودين
    |       ├── tool_registry.py —— نظام الملحقات
    |       ├── tools.py —— 30+ أداة مدمجة
    |       ├── compaction.py —— إدارة نافذة السياق
    |       ├── governance.py —— حوكمة الميزانية/الأذونات
    |       └── multi_agent/ —— الوكلاء الفرعيون (القطيع)
    |
    ├── context.py —— منشئ موجه النظام
    |       └── memory/ —— MemPalace الذاكرة الدلالية
    |
    ├── skill/ —— نظام المهارات
    ├── checkpoint/ —— لقطات + إرجاع
    ├── plugin/ —— نظام المحول التلقائي
    ├── voice/ —— STT (Whisper) + TTS (متعدد المحركات)
    ├── task/ —— إدارة المهام
    ├── webbridge/ —— أتمتة Playwright
    └── dulus_mcp/ —— عميل MCP
```

---

## القطيع (الوكلاء الفرعيون)

يمكن لـ Dulus إنشاء وكلاء مكتوبين يعملون في**git worktrees معزولة**.

```
/agents
Agent(type="coder",    task="refactor auth")
Agent(type="reviewer", task="review #042")
Agent(type="tester",   task="run e2e on auth")
```

---

## الأذونات

| الوضع | السلوك |
|---|---|
| `auto` *(افتراضي)* | القراءة مسموحة دائماً. السؤال قبل الكتابة/shell. |
| `accept-all` | بدون موجهات. كل شيء معتمد تلقائياً. **YOLO.** |
| `manual` | سؤال لكل عملية. |
| `plan` | للقراءة فقط. ملف الخطة فقط قابل للكتابة. |

---

## أوامر Slash

| الأمر | الوصف |
|---|---|
| `/model [الاسم]` | عرض أو تبديل النموذج |
| `/memory [استعلام]` | الذاكرة الدلالية المستمرة |
| `/voice` | إدخال صوتي (Whisper بدون اتصال) |
| `/brainstorm [الموضوع]` | مجلس الأشباح |
| `/ssj` | قائمة الطاقة (10 اختصارات) |
| `/telegram [الرمز] [المعرف]` | جسر Telegram |
| `/checkpoint [المعرف]` | قائمة / إرجاع نقاط التفتيش |
| `/plan [الوصف]` | دخول / خروج وضع الخطة |
| `/lang [الرمز]` | تبديل اللغة (34 رمزاً) |
| `/cost` | الرموز والمستهلكة بالدولار |
| `/help` | جميع الأوامر |

---

## توكن $DULUS

**العقد:** `9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump`

توكن $DULUS هو طبقة الوقود لنظام Dulus البيئي. REPL مفتوح المصدر يبقى مجانياً للأبد —— $DULUS هو مفتاح طبقة الأعمال.

| المرحلة | الفائدة |
|---|---|
| **الآن** | ملكية مجتمعية. مكافآت مقفلة on-chain |
| **Business v1** | وصول مبكر + خصومات للحائزين |
| **الرصيد** | دفع رصيد API بـ $DULUS |
| **النشر** | تدوير مثيلات سحابية بالدفع بـ $DULUS |
| **الاشتراكات** | اشتراك شهري بالدفع بـ $DULUS |
| **الحوكمة** | كبار الحائزين يصوتون على أولويات الميزات |

---

## الترخيص

GPLv3. انسخه، عدّله، أعد توزيعه —— لكن احتفظ به مفتوحاً.

> *سُمي على شرف الطائر، وليس الصاروخ. نستمر في الطيران.*

---

<div align="center">

<p><sub>بُني بالمخالب بواسطة <a href="https://github.com/KevRojo">KevRojo</a> · سانتو دومينغو، جمهورية الدومينيكان · 2026</sub></p>

</div>
