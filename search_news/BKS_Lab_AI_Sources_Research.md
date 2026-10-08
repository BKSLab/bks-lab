# BKS Lab — карта источников об искусственном интеллекте

**Исследовательский каталог для редакционного News Analyzer и личного изучения AI**\
**Дата подготовки:** 8 октября 2026 года. **Языки:** русский и английский.

## 0. Как пользоваться

Каталог решает две задачи: (1) находить новости и материалы для BKS Lab, (2) систематически учиться AI-разработке, корпоративному внедрению, политике, этике, культуре и философии AI.

**Обозначения:** `RSS` — известный адрес feed; `API` — документированный API; `HTML` — мониторинг публикаций через парсер сайта; `READ` — особенно ценен для вдумчивого чтения. `A` — подключать в первую очередь; `B` — расширение; `C` — читать/проверять время от времени. **Важно:** наличие RSS не гарантирует, что URL отвечает из конкретного сервера или не изменится. Перед добавлением выполнять HTTP-проверку и предпросмотр; для адресов без явной проверки пометка «проверить при интеграции». Не трактовать новости вендоров как независимые оценки.

## 1. Официальные лаборатории и модели (англ.)

| Приоритет | Источник | Адрес сайта | Подключение | Почему важно |
|---|---|---|---|---|
| A | OpenAI News | https://openai.com/news/ | HTML, autodiscovery RSS | Новые модели, API, безопасность, корпоративные продукты; первоисточник |
| A | Anthropic News | https://www.anthropic.com/news | HTML | Claude, работа агентов, safety, бизнес; не полагаться на непроверенный RSS |
| A | Google DeepMind | https://deepmind.google/discover/blog/ | HTML, autodiscovery | Научные работы, модели, исследования |
| A | Google AI Blog | https://blog.google/technology/ai/ | HTML, autodiscovery | AI-продукты и широкий технологический контекст |
| A | Hugging Face Blog | https://huggingface.co/blog | RSS: https://huggingface.co/blog/feed.xml | Open-weight модели, библиотеки, прикладные исследования; при парсинге учитывать, что некоторые записи имеют URL в GUID вместо link |
| A | Meta AI | https://ai.meta.com/blog/ | HTML | Llama и исследования Meta |
| A | Microsoft Research | https://www.microsoft.com/en-us/research/blog/ | HTML/RSS autodiscovery | Корпоративные исследования, агенты, качество систем |
| A | Microsoft Azure AI | https://techcommunity.microsoft.com/category/azure-ai-services/blog/azure-ai-services-blog | HTML | Практика enterprise AI и облачной интеграции |
| A | Mistral AI News | https://mistral.ai/news | HTML, RSS проверить | Европейские модели, open-weight и enterprise |
| B | NVIDIA AI Blog | https://blogs.nvidia.com/blog/category/ai/ | HTML | Инфраструктура, inference, бизнес-кейсы |
| B | Cohere Blog | https://cohere.com/blog | HTML | Retrieval, корпоративные LLM и безопасность данных |
| B | AWS Machine Learning | https://aws.amazon.com/blogs/machine-learning/ | HTML/RSS autodiscovery | Production ML и GenAI в компаниях |
| B | IBM Research AI | https://research.ibm.com/artificial-intelligence | HTML | Enterprise AI, governance, научные разработки |
| B | Qwen | https://qwenlm.github.io/ | HTML | Открытые модели и технические релизы |
| B | DeepSeek | https://api-docs.deepseek.com/news | HTML | Обновления моделей и API; проверить актуальность страницы |

**Редакционный принцип:** первоисточники отлично подходят для *обнаружения* событий, но заявления о достижениях сверять по независимым оценкам и исследованиям.

## 2. AI-разработка, код, агенты, RAG и инженерные практики

| Приоритет | Источник | URL | Подключение | Польза |
|---|---|---|---|---|
| A | Simon Willison | https://simonwillison.net/ | Atom (лонгриды): https://simonwillison.net/atom/entries/ ; всё: https://simonwillison.net/atom/everything/ | Практика LLM, prompt injection, инструменты, оценка моделей, разработка; READ |
| A | Lilian Weng | https://lilianweng.github.io/ | HTML | Глубокие технические обзоры LLM, агентов, RL; READ |
| A | Chip Huyen | https://huyenchip.com/blog/ | HTML | AI Engineering, inference, ML-продукты и эксплуатация; READ |
| A | Hugging Face Papers | https://huggingface.co/papers | HTML | Обзор новых научных работ |
| A | LangChain Blog | https://blog.langchain.com/ | HTML/RSS autodiscovery | Агентные системы, наблюдаемость, evals; учитывать коммерческую заинтересованность |
| A | LlamaIndex Blog | https://www.llamaindex.ai/blog | HTML | RAG, контекст, подключение корпоративных данных |
| A | arXiv cs.AI | https://arxiv.org/list/cs.AI/recent | RSS: https://rss.arxiv.org/rss/cs.AI | Исследования по искусственному интеллекту |
| A | arXiv cs.CL | https://arxiv.org/list/cs.CL/recent | RSS: https://rss.arxiv.org/rss/cs.CL | LLM, NLP, reasoning |
| A | arXiv cs.LG | https://arxiv.org/list/cs.LG/recent | RSS: https://rss.arxiv.org/rss/cs.LG | Обучение и оценка моделей |
| B | Full Stack Deep Learning | https://fullstackdeeplearning.com/ | HTML | Системная практика ML/LLM-продуктов; READ |
| B | Eugene Yan | https://eugeneyan.com/ | HTML/RSS autodiscovery | Recommendation, LLM, production ML, evals; READ |
| B | Hamel Husain | https://hamel.dev/ | HTML | AI-оценивание, прикладная инженерия, обучение; READ |
| B | Sebastian Raschka | https://sebastianraschka.com/blog/ | HTML/RSS autodiscovery | Устройство LLM, архитектуры, тренинг; READ |
| B | Martin Fowler | https://martinfowler.com/ | RSS: https://martinfowler.com/feed.atom | Архитектура, инженерная дисциплина, материалы об AI-разработке |
| B | GitHub Blog: AI | https://github.blog/ai-and-ml/ | HTML | AI coding, инструменты, workflow разработчиков |

## 3. AI в бизнесе, компаниях и B2B

| Приоритет | Источник | URL | Подключение | На что смотреть |
|---|---|---|---|---|
| A | Ethan Mollick / One Useful Thing | https://www.oneusefulthing.org/ | HTML, RSS autodiscovery; READ | Как AI влияет на труд, обучение, организации и управление; авторский взгляд |
| A | MIT Sloan Management Review / AI | https://sloanreview.mit.edu/tag/artificial-intelligence/ | HTML; READ | Практика компаний, стратегия, организационные изменения |
| A | Harvard Business Review / AI | https://hbr.org/topic/subject/artificial-intelligence | HTML, часть материалов закрыта; READ | Лидерство, управление, операционные процессы |
| A | McKinsey / AI | https://www.mckinsey.com/capabilities/quantumblack/our-insights | HTML | Исследования внедрения, ROI и корпоративной зрелости; проверять методики |
| A | Stanford HAI AI Index 2026 | https://hai.stanford.edu/ai-index/2026-ai-index-report | HTML, периодические отчёты; READ | Проверяемые цифры об AI, экономике, занятости, политике и обществе |
| A | Microsoft WorkLab | https://www.microsoft.com/en-us/worklab/ | HTML | AI на рабочих местах и корпоративные процессы; vendor viewpoint |
| B | Gartner AI | https://www.gartner.com/en/topics/artificial-intelligence | HTML, часто платно | Рыночные категории, enterprise-аналитика |
| B | Deloitte Insights / AI | https://www.deloitte.com/global/en/insights/topics/ai.html | HTML | Бизнес-внедрение и риски |
| B | IBM Think / AI | https://www.ibm.com/think/topics/artificial-intelligence | HTML | Enterprise AI, интеграция, governance |
| B | VentureBeat AI | https://venturebeat.com/ai/ | HTML/RSS autodiscovery | Оперативная журналистика о внедрении AI |
| B | The Batch (DeepLearning.AI) | https://www.deeplearning.ai/the-batch/ | HTML/newsletter | Качественные обзоры AI для практиков |

**В редакционной политике:** отделить заявленный ROI поставщика от независимых исследований; фиксировать масштабы выборки, отрасль и условия внедрения.

## 4. Этические, политические, правовые и философские вопросы

| Приоритет | Источник | URL | Подключение | Польза |
|---|---|---|---|---|
| A | AI Now Institute | https://ainowinstitute.org/ | HTML; READ | Власть, труд, корпоративное влияние, социальные последствия |
| A | Ada Lovelace Institute | https://www.adalovelaceinstitute.org/ | HTML; READ | Общественный интерес, права, governance |
| A | OECD AI Policy Observatory | https://oecd.ai/ | HTML/данные | Международные политики, статистика, регулирование |
| A | EU AI Act official | https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai | HTML | Первичный контекст регулирования ЕС |
| A | NIST AI Risk Management Framework | https://www.nist.gov/itl/ai-risk-management-framework | HTML | Практическое управление AI-рисками |
| A | Stanford HAI Policy | https://hai.stanford.edu/policy | HTML | Исследования о регулировании и общественных последствиях |
| A | Center for AI Safety | https://www.safe.ai/ | HTML; READ | Риски мощных AI-систем; одна из позиций дискуссии |
| A | METR | https://metr.org/ | HTML | Независимые измерения возможностей агентов и связанных рисков |
| B | AI Incident Database | https://incidentdatabase.ai/ | HTML | Реальные инциденты и отказоустойчивость |
| B | Partnership on AI | https://partnershiponai.org/ | HTML | Ответственные практики AI и governance |
| B | Future of Life Institute | https://futureoflife.org/ | HTML; READ | Долгосрочные последствия и позиции об AI-рисках |
| B | The Gradient | https://thegradient.pub/ | HTML | Глубокие эссе об исследованиях и последствиях AI |
| B | Noema Magazine | https://www.noemamag.com/ | HTML; READ | Философия, культура, технологии и будущее общества |
| B | Aeon | https://aeon.co/ | HTML; READ | Философские эссе о сознании, человеке и технологиях |
| B | MIT Technology Review — AI | https://www.technologyreview.com/topic/artificial-intelligence/ | HTML, местами paywall | Журналистский разбор социальных и технических вопросов |
| B | Nature Machine Intelligence | https://www.nature.com/natmachintell/ | HTML/RSS autodiscovery, часть платно | Научная перспектива, этика, обществознание |

## 5. Личные сайты и голоса, которые стоит читать напрямую

Особенно важно **читать позиции, которые расходятся друг с другом**: оптимистические, скептические, safety-oriented, критико-социальные и инженерные.

| Автор | Сайт | Почему следить | Подключение |
|---|---|---|---|
| Simon Willison | https://simonwillison.net/ | Чрезвычайно прикладной независимый голос об LLM и AI coding | Atom, A |
| Ethan Mollick | https://www.oneusefulthing.org/ | AI и работа людей, изменение компаний, образование | HTML/автопоиск ленты, A |
| Andrej Karpathy | https://karpathy.ai/ | Глубокое объяснение нейросетей, LLM и нового типа разработки | HTML, READ |
| Andrew Ng | https://www.andrewng.org/ | Практический взгляд на развитие AI-продуктов и образование | HTML/рассылки, READ |
| Lilian Weng | https://lilianweng.github.io/ | Большие технические обзоры агентов, LLM и исследований | HTML, A |
| Chip Huyen | https://huyenchip.com/ | Инженерия AI-систем и production-практики | HTML, A |
| Sebastian Raschka | https://sebastianraschka.com/ | Понятно и глубоко про архитектуры моделей | HTML, B |
| Gary Marcus | https://garymarcus.substack.com/ | Скептический взгляд на возможности моделей и заявления компаний | HTML/рассылка, A |
| Yoshua Bengio | https://yoshuabengio.org/ | Исследования и обеспокоенность AI-безопасностью | HTML, A |
| Geoffrey Hinton | https://www.cs.toronto.edu/~hinton/ | Фундаментальные идеи deep learning; сайт больше архивный, чем новостной | READ, C |
| Yann LeCun | https://yann.lecun.com/ | Фундаментальная наука, позиция по развитию AI; сайт преимущественно архив | READ, C |
| Richard Sutton | http://incompleteideas.net/ | Обучение с подкреплением, теоретические основания AI | READ, C |
| Eliezer Yudkowsky | https://www.lesswrong.com/users/elizeryudkowsky | Радикальная позиция об AI-рисках; читать критически | HTML, B |
| Scott Alexander | https://www.astralcodexten.com/ | Аналитические эссе, политическая философия и AI | HTML, B |
| Zvi Mowshowitz | https://thezvi.substack.com/ | Детальные обзоры дискуссий о перспективах и рисках AI | HTML, B |
| Jürgen Schmidhuber | https://people.idsia.ch/~juergen/ | История AI, развитие архитектур; преимущественно архивные материалы | READ, C |

Примечание: адреса авторских площадок — отправные точки. Не у каждого исследователя есть регулярный личный RSS или блог; не притворяться, что архивный академический сайт — новостная лента.

## 6. Русскоязычные источники

| Приоритет | Источник | URL | Подключение | Ценность и ограничения |
|---|---|---|---|---|
| A | Хабр — Искусственный интеллект | https://habr.com/ru/hubs/artificial_intelligence/ | HTML, RSS autodiscovery | Кейсы, переводы, инженерная практика; качество отдельных статей неравномерно |
| A | Хабр — Машинное обучение | https://habr.com/ru/hubs/machine_learning/ | HTML, RSS autodiscovery | ML, LLM, внедрение, инструменты |
| A | Tproger | https://tproger.ru/ | HTML/RSS autodiscovery | Прикладная разработка, инструменты, оперативные темы |
| A | Код Дурова | https://kod.ru/ | HTML | Технологическая повестка и AI в продуктах |
| A | N+1 | https://nplus1.ru/ | HTML, RSS autodiscovery | Научные работы и общественный контекст |
| A | ТАСС — Наука | https://nauka.tass.ru/ | HTML | Новости исследований и решений, использовать первоисточники |
| B | CNews — Искусственный интеллект | https://www.cnews.ru/tags/iskusstvennyj_intellekt | HTML | Российский корпоративный IT и B2B-проекты |
| B | ComNews | https://www.comnews.ru/ | HTML | Корпоративная цифровизация, инфраструктура, рынок |
| B | РБК Тренды | https://trends.rbc.ru/ | HTML | AI, экономика, общество, будущее профессий |
| B | Forbes Russia | https://www.forbes.ru/ | HTML | Экономика и корпоративное внедрение; часть материалов может быть закрыта |
| B | ПостНаука | https://postnauka.org/ | HTML; READ | Научные и философские объяснения, преимущественно evergreen |
| B | Горький | https://gorky.media/ | HTML; READ | Культурно-философская перспектива, не ежедневные AI-новости |
| B | Сбер AI | https://developers.sber.ru/ | HTML | Российские модели/инструменты, vendor viewpoint |
| B | Yandex Research | https://research.yandex.com/ | HTML | Исследования, ML, модели; проверять актуальные публикации |
| B | Т-Банк AI Research | https://research.tbank.ru/ | HTML | Прикладные исследования и корпоративный ML; проверить структуру публикаций |

**Для российской повестки:** отдельно подтверждать правовые заявления по официальным документам, а не по пересказам СМИ.

## 7. Бесплатные API и поисковые ресурсы

| Инструмент | Документация / endpoint | Как использовать | Ограничение |
|---|---|---|---|
| Hacker News Algolia Search | https://hn.algolia.com/api | `https://hn.algolia.com/api/v1/search_by_date?query=LLM&tags=story` | Бесплатный публичный поиск, лимиты и правила сервиса |
| arXiv API | https://info.arxiv.org/help/api/ | Поиск работ по категориям и ключевым словам | Работы — препринты, не все прошли рецензирование |
| arXiv RSS | https://rss.arxiv.org/rss/cs.AI | Новости научных публикаций | Высокий поток, нужен жёсткий отбор |
| GitHub REST API | https://docs.github.com/en/rest/releases/releases | Следить за новыми релизами конкретных репозиториев | Rate limits, токен может понадобиться для стабильной работы |
| Crossref REST API | https://api.crossref.org/ | DOI, библиография, поиск публикаций | Не обязательно полный текст |
| OpenAlex API | https://docs.openalex.org/ | Научные работы, авторы, организации, темы | Проверять актуальные лимиты и условия доступа |
| Semantic Scholar API | https://api.semanticscholar.org/api-docs/ | Поиск научных работ и метаданных | Rate limits, возможны ограничения |
| GDELT | https://www.gdeltproject.org/ | Анализ глобального новостного контекста | Сложнее, шумно, требует тематической фильтрации |
| SearXNG (self-hosted) | https://docs.searxng.org/ | Собственный метапоиск по запросам, JSON при включении | Использует внешние движки; капчи и блокировки возможны |
| HN RSS | https://hnrss.org/ | Готовые RSS-ленты и тематические фильтры | Сообщество, не подтверждение достоверности |

**SearXNG не равен собственной поисковой индексации:** это агрегатор запросов к внешним системам. У бесплатных API тоже бывают квоты, изменения условий и rate limits; мониторить ошибки.

## 8. Темы для поиска (сохранённые поисковые задания)

### AI-разработка
`AI coding agents`, `LLM agent evaluations`, `agentic software engineering`, `LLM observability`, `prompt injection`, `RAG production`, `model context protocol`, `AI software architecture`, `open-weight LLM releases`.

### AI в корпорациях и B2B
`enterprise generative AI ROI`, `AI in customer support B2B`, `LLM enterprise security`, `AI governance in companies`, `AI workflow automation`, `AI business process redesign`, `human in the loop enterprise AI`, `AI adoption workforce`.

### Этическая, общественная и философская повестка
`AI and labor displacement`, `AI consciousness debate`, `AI moral status`, `AI regulation EU`, `AI power concentration`, `AI geopolitical competition`, `AI and democracy`, `AI epistemology`, `AI cultural change`, `AGI governance`.

### Русские запросы
`ИИ-агенты в корпоративных процессах`, `внедрение генеративного ИИ в B2B`, `экономика внедрения ИИ`, `ИИ и рынок труда`, `правовое регулирование искусственного интеллекта`, `этика ИИ`, `ИИ и философия сознания`, `открытые языковые модели`, `разработка с ИИ`.

Поисковые задания хранить отдельно от источников и запускать с ограничениями объёма, периода, числа запросов и доменов.

## 9. Рекомендуемый стартовый набор для News Analyzer

Не подключать все источники сразу: это увеличит шум и расход на LLM. Начать с **18**:

1. Simon Willison — Atom long-form (AI-разработка).
2. Hugging Face Blog — RSS (модели и инструменты).
3. OpenAI News — HTML (релизы).
4. Anthropic News — HTML (модели и агенты).
5. Google DeepMind Blog — HTML (исследования).
6. Mistral News — HTML (модели).
7. GitHub Releases по избранным AI-проектам — API.
8. Hacker News Algolia по 3–5 запросам — API.
9. arXiv cs.AI — RSS, с высокой отсечкой релевантности.
10. Lilian Weng — HTML (длинные технические статьи).
11. Chip Huyen — HTML (AI Engineering).
12. Ethan Mollick — HTML (бизнес, труд, обучение).
13. MIT Sloan Management Review — HTML (управление).
14. Stanford HAI — HTML (данные, политика).
15. AI Now Institute — HTML (социальные вопросы).
16. OECD AI Policy Observatory — HTML (политика и нормы).
17. Хабр, хаб «Искусственный интеллект» — HTML.
18. N+1 — HTML (русскоязычная наука).

Для личного чтения независимо от автоматической ленты: Karpathy, Bengio, Marcus, Sutton, Noema, Aeon, AI Index 2026 и исследовательские отчёты. Это углубляет понимание, а не только скорость реакции на релизы.

## 10. Редакционная политика и цикл обучения

Разделить источники по типам: **первичные** (лаборатории, публикации), **независимая аналитика**, **корпоративные кейсы**, **мнения/эссе**, **агрегаторы**. Присвоить рейтинг надёжности на уровне источника и отдельный флаг `vendor_affiliated`. Модель ранжирует соответствие тематике, не объявляя мнение доказанным фактом.

Рекомендованные рубрики BKS Lab:
- AI Engineering / Разработка с ИИ
- Модели и исследования
- AI в бизнесе и B2B
- Корпоративные AI-системы и агенты
- Экономика и рынок труда
- Политика, право и регулирование
- Общество, культура и философия
- Безопасность, надёжность и этика
- Будущее AI и человека

В карточке материала сохранять: оригинальное название, оригинальный язык, дату, источник, URL, метод получения, рубрики/темы, аннотацию, комментарий LLM, два независимых score (новость/статья), ссылку на первичное исследование при наличии, статус проверки.

**Личный режим изучения:** каждую неделю 2 инженерных материала + 1 B2B-кейс + 1 исследование или философское эссе. Для каждого сохранить 3 тезиса: «что узнал», «с чем не согласен», «как применить в своих проектах». Отдельно отмечать идеи для авторской аналитики BKS Lab.

## 11. Контроль качества ссылок и правовые ограничения

1. Выполнить live `discover`/HTTP-проверку каждого URL перед включением (редиректы, 200, content-type, RSS parsing, дата последнего элемента).
2. Для RSS сохранять GUID, ETag/Last-Modified и canonical URL; если feed возвращает GUID вместо `<link>`, использовать GUID как возможную ссылку только после валидации.
3. Для HTML без RSS использовать осторожный парсинг и ограничение частоты. Если источник закрыт/платный, сохранять только публичную карточку и ссылку.
4. Не копировать материалы целиком на публичный сайт. Писать самостоятельные тексты, цитировать кратко, давать ссылки на первоисточники.
5. Проверять независимыми источниками сенсационные утверждения об AGI, трудоустройстве, рисках и эффективности.
6. Раз в квартал пересматривать каталог: умершие RSS, смены URL, источники с низкой полезностью, новые авторы.

## 12. Проверенные опорные страницы для проекта

- Simon Willison: официальные Atom feeds перечислены на https://simonwillison.net/about/
- Hugging Face: обсуждение структуры RSS и URL https://discuss.huggingface.co/t/blog-rss-feed-missing-link-tag/146539
- Hacker News Algolia: документация API https://hn.algolia.com/api
- Stanford HAI: 2026 AI Index https://hai.stanford.edu/ai-index/2026-ai-index-report
- Хабр: справочник хабов и тем https://habr.com/ru/hubs/

**Статус проверки:** страницы и перечисленные выше официальные опорные ресурсы проверены поиском в ходе подготовки. Остальные сайты подобраны по известным официальным адресам, однако полная автоматическая HTTP/RSS-валидация каждого endpoint не выполнялась. Не считать пометку RSS/API гарантией доступности без теста из инфраструктуры BKS Lab.
