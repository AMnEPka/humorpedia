# R13k — точное восстановление оставшихся prefix/path href

Дата:23.10.2026. Статус: **согласовано и принято на изолированной копии23.10.2026; опубликовано8ddd396, GitHub CI success**.

Ветка `codex/local-page-builder`, worktree `r5-zip-operations/humorpedia`, HEAD `5ab9154c14f475ef06fe8aa3ec34aaa786e52821`.

## Результат исследования и границы

После принятого R13j осталось249 unresolved keys. Из103 оставшихся ключей прежней группы «один slug-кандидат» предложены102 точные замены: **782 href в548 полях422 published документов, включая9 hidden occurrences;99 целевых страниц**. Пользователь23.10 подтвердил весь пакет. Все782 href применены только в новой изолированной копии; API/HTTP/browser-приёмка завершена успешно.

Каждая цель сверена с canonical URL текущего URL_BUILDERS, published-статусом, target old_id, точным ресурсом MODX и контекстом ссылки. Совпадение последнего slug само по себе недостаточно. В код resolver не добавляется общий fallback; старые подписи, включая исторические названия и пунктуационные anchors, сохраняются. Hidden поля перечислены в том же exact-span плане; скрытые модули не включаются публично.

Исходник `.cache/r13j/copy/patched.jsonl`:25,620 projected records, SHA256 `90e38c00f870bcbf28702675097eb752b8304148f5556d61d481e8985f9e4ea7`. Field plan `.cache/r13k/exact-href-plan.json`: SHA256 `b8f9a556bba7c9b3fd7b05873225b19e2299eebd7cc30a0a57f78281b791d3d2`; unsupported quoted href0. В полном SQL использовалась только публичная таблица ресурсов, SHA256 `d4a2e0930ebc676aca939ad569c54bc82e7470184ca0c40ede63e9a19898cf19`.

Машиночитаемая [таблица102 mappings](r13k-exact-href-proposal-2026-10-23.json) содержит typed target IDs, MODX IDs/URI/строки, подписи и буквальные href-варианты. Полный span-план и исходные данные остаются в ignored `.cache`; их SHA закреплён для проверки перед исполнением.

## Важные решения внутри предлагаемого пакета

- `kvn/teams/vladivostok` ведёт на **команду** `/kvn/teams/sbornaya-vladivostoka` (old_id2373): подписи «Сборная Владивостока». Кандидат `/city/vladivostok` отклонён.
- Склеенный `liga-gorodov/team/izhitsa.htmlhttps:/humorpedia.ru/kvn/team/macleod` ведёт на `/shows/liga-gorodov/teams/izhitsa` (old_id1935). В биографии Максима Снигирёва явно указаны «Лига Городов» и команда «Ижица». Не выбирать MacLeod по последнему фрагменту.
- `kvnteam/sbornaya-buvshikh`: target history прямо говорит, что до сезона2018 команда называлась «Сборная Тульской области». Историческая подпись остаётся.
- easycom/«Натальная карта», «Импровизация»/«Импровизаторы», О.С.П./«33 квадратных метра» сверены с историей существующих целевых карточек. Сохраняется авторская ссылка на ту же сущность, без создания новых страниц или редакционной замены текста.
- Для KVN teams действующий контракт `show_id:null` включает отсутствие поля; show-team «Женщины» использует `/shows/zvezdy-ntv/teams/zhenshchiny`. Обязательное поле team_type не вводится.

**Исключение:** `kvn/kivin/kivin-2024` остаётся unresolved: исходная страница фестиваля — MODX1614, новость `/news/kivin-2024` — MODX2377. Это разные материалы; найденную новость не подставлять. Ещё146 ключей других групп также вне пакета. Offline аудит реального resolver подтвердил249→147 unresolved; оставшийся набор равен прежнему минус102 согласованных keys. Это не HTTP-утверждение о147 ошибках.

## Согласованный план реализации

| Шаг | Результат и проверка | Модель |
|---|---|---|
|1. Подготовить новую копию | Проверить source/plan SHA, typed IDs и preimage548 полей; применить только782 разрешённых href; исходный R13j не менять | Sol/high |
|2. Независимая сверка | Все25,620 records: ровно422 docs изменены, только согласованные spans; подписи/прочие attrs/query/fragment/медиа/связи/R13i сохранены; hidden9 проверены offline | Luna/high для независимой сверки |
|3. Реальный resolver | Повторить аудит всех links, доказать отсутствие новых ошибок и исключение festival→news; измерить остаток, не предполагать147 | Sol/high |
|4. Native API/HTTP | Owned UUID DB/network без host ports; serving только внутри пилота,indexing=false;422 sources+99 targets, канонические href и доступность; snapshot/media read-only | Sol/high |
|5. Browser | Реальные переходы: kvnteam/proekty/вложенные shows, Владивосток-команда, Ижица-шоу, исторические labels; отсутствие pageerrors; hidden не раскрывать | Sol/high |
|6. Завершение | Проверить25,620 записей после запросов, допуская только штатные views; cleanup UUID resources; read-only контроль main/HTTP/Docker; обновить приёмку | Sol/high |

Новый backend/frontend код в пакете не запланирован; при неизменном коде полный backend повторно не гонять без причины. Использовать принятые R13j guard checks, обновив закреплённые SHA/counts для нового пакета. Выявленное необходимое изменение поведения сначала обсудить.

Не запускать dev-sync/export-local из worktree, не останавливать основные контейнеры. Полный release archive и demo-exclude policy, поиск8 оригинальных posters, external/embed111, интеграция и включение индексации — последующие отдельные этапы. Основной main, импорт24СМИ и VPS не затрагиваются.

## Точная таблица

| Исходный key | Canonical target | MODX ID | href |
|---|---|---:|---:|
| `Improv/gromkiy-vopros` | `/shows/medium-quality/improkom/gromkiy-vopros` | 1682 | 1 |
| `dvij/jam` | `/shows/medium-quality/dvij/jam` | 1774 | 5 |
| `eople/vadim-postilnyij` | `/people/vadim-postilnyij` | 177 | 1 |
| `kvn/teams/vladivostok` | `/kvn/teams/sbornaya-vladivostoka` | 2373 | 8 |
| `kvn/vysshaya-liga/referee-vysshaya-liga` | `/kvn/vl-kvn/referee-vysshaya-liga` | 1517 | 3 |
| `kvnteam/25` | `/kvn/teams/25` | 1046 | 1 |
| `kvnteam/asia-mix` | `/kvn/teams/asia-mix` | 1092 | 2 |
| `kvnteam/bdsm` | `/kvn/teams/bdsm` | 1124 | 2 |
| `kvnteam/brodyagi` | `/kvn/teams/brodyagi` | 1087 | 1 |
| `kvnteam/chistye-prudy` | `/kvn/teams/chistye-prudy` | 1118 | 2 |
| `kvnteam/chp` | `/kvn/teams/chp` | 1044 | 2 |
| `kvnteam/dals` | `/kvn/teams/dals` | 1034 | 1 |
| `kvnteam/devchonki` | `/kvn/teams/devchonki` | 1100 | 2 |
| `kvnteam/dlsh` | `/kvn/teams/dlsh` | 1054 | 1 |
| `kvnteam/doktor-hauss` | `/kvn/teams/doktor-hauss` | 1099 | 1 |
| `kvnteam/electroshock` | `/kvn/teams/electroshock` | 1127 | 1 |
| `kvnteam/g-drive` | `/kvn/teams/g-drive` | 1121 | 2 |
| `kvnteam/holodnie-goroda` | `/kvn/teams/holodnie-goroda` | 1130 | 1 |
| `kvnteam/imenimenya` | `/kvn/teams/imenimenya` | 1040 | 2 |
| `kvnteam/krasniy-lis` | `/kvn/teams/krasniy-lis` | 1102 | 1 |
| `kvnteam/mdudikov` | `/kvn/teams/mdudikov` | 1052 | 1 |
| `kvnteam/megapolis` | `/kvn/teams/megapolis` | 1039 | 1 |
| `kvnteam/napoleon-dinamit` | `/kvn/teams/napoleon-dinamit` | 1038 | 3 |
| `kvnteam/ne-takaya` | `/kvn/teams/ne-takaya` | 1079 | 1 |
| `kvnteam/neudergimyij-djo` | `/kvn/teams/neudergimyij-djo` | 1093 | 2 |
| `kvnteam/novyie-armyane` | `/kvn/teams/novyie-armyane` | 1053 | 1 |
| `kvnteam/planeta-sochi` | `/kvn/teams/planeta-sochi` | 1116 | 2 |
| `kvnteam/poligraf` | `/kvn/teams/poligraf` | 1042 | 1 |
| `kvnteam/proigryivatel` | `/kvn/teams/proigryivatel` | 1085 | 1 |
| `kvnteam/radio-svoboda` | `/kvn/teams/radio-svoboda` | 1119 | 1 |
| `kvnteam/rosatom` | `/kvn/teams/rosatom` | 1115 | 1 |
| `kvnteam/royalflush` | `/kvn/teams/royalflush` | 1037 | 1 |
| `kvnteam/rudn-united` | `/kvn/teams/rudn-united` | 1104 | 2 |
| `kvnteam/russkaya-doroga` | `/kvn/teams/russkaya-doroga` | 1069 | 1 |
| `kvnteam/sbornaya-buvshikh` | `/kvn/teams/sbornaya-buvshikh` | 1105 | 1 |
| `kvnteam/sbornaya-murmanska` | `/kvn/teams/sbornaya-murmanska` | 1107 | 1 |
| `kvnteam/semejnyie-shtuchki` | `/kvn/teams/semejnyie-shtuchki` | 1103 | 1 |
| `kvnteam/sportivnaya` | `/kvn/teams/sportivnaya` | 1041 | 1 |
| `kvnteam/tak-to` | `/kvn/teams/tak-to` | 1045 | 2 |
| `kvnteam/uralskie-dvorniki` | `/kvn/teams/uralskie-dvorniki` | 1083 | 1 |
| `kvnteam/volzhane` | `/kvn/teams/volzhane` | 1136 | 3 |
| `kvnteam/ya-obidelas` | `/kvn/teams/ya-obidelas` | 1096 | 3 |
| `kvnteam/yura` | `/kvn/teams/yura` | 1114 | 1 |
| `kvnteam/zabaykalsky-krai` | `/kvn/teams/zabaykalsky-krai` | 1120 | 1 |
| `liga-gorodov/team/izhitsa.htmlhttps:/humorpedia.ru/kvn/team/macleod` | `/shows/liga-gorodov/teams/izhitsa` | 1935 | 1 |
| `medium-quality/cbd` | `/shows/cbd` | 1735 | 8 |
| `novosti/kvn/team/ue` | `/kvn/teams/ue` | 1063 | 2 |
| `novosti/people/konstantin-belevtsev` | `/people/konstantin-belevtsev` | 654 | 2 |
| `people/kvn/team/sok` | `/kvn/teams/sok` | 1183 | 2 |
| `people/proekty/standupclub1` | `/shows/standupclub1` | 1631 | 2 |
| `proekty/22-komika` | `/shows/22-komika` | 1653 | 3 |
| `proekty/bar-v-bolshom-gorode` | `/shows/bar-v-bolshom-gorode` | 1627 | 1 |
| `proekty/big-show` | `/shows/big-show` | 1656 | 22 |
| `proekty/central-microphone` | `/shows/central-microphone` | 1648 | 2 |
| `proekty/comedy-battle` | `/shows/comedy-battle` | 1629 | 2 |
| `proekty/comedy-club` | `/shows/comedy-club` | 1615 | 2 |
| `proekty/comedywoman` | `/shows/comedywoman` | 1622 | 26 |
| `proekty/improv` | `/shows/improv` | 1619 | 7 |
| `proekty/improv-teams` | `/shows/improv-teams` | 1618 | 1 |
| `proekty/komandy` | `/shows/komandy` | 3678 | 8 |
| `proekty/leningradskij-stand-up-club` | `/shows/leningradskij-stand-up-club` | 1647 | 1 |
| `proekty/medium-quality` | `/shows/medium-quality` | 1630 | 22 |
| `proekty/medium-quality/bad-company` | `/shows/medium-quality/bad-company` | 2253 | 3 |
| `proekty/medium-quality/cbd` | `/shows/cbd` | 1735 | 13 |
| `proekty/medium-quality/easycom` | `/shows/medium-quality/easycom` | 2279 | 3 |
| `proekty/medium-quality/kanal-azamata-musagalieva` | `/shows/medium-quality/kanal-azamata-musagalieva` | 2295 | 1 |
| `proekty/medium-quality/komyuniti` | `/shows/medium-quality/komyuniti` | 2288 | 1 |
| `proekty/medium-quality/labelcom` | `/shows/medium-quality/labelcom` | 2280 | 4 |
| `proekty/medium-quality/labelplay` | `/shows/medium-quality/labelplay` | 2283 | 2 |
| `proekty/medium-quality/labelsmart` | `/shows/medium-quality/labelsmart` | 2284 | 5 |
| `proekty/medium-quality/lena-kuka-crew` | `/shows/lena-kuka-crew` | 2285 | 3 |
| `proekty/medium-quality/match` | `/shows/medium-quality/match` | 2290 | 1 |
| `proekty/medium-quality/money-mic` | `/shows/money-mic` | 2289 | 8 |
| `proekty/medium-quality/outside-stand-up` | `/shows/medium-quality/outside-stand-up` | 1732 | 6 |
| `proekty/medium-quality/ploshchadka` | `/shows/medium-quality/ploshchadka` | 2292 | 2 |
| `proekty/medium-quality/proekty-mq-i-winline` | `/shows/medium-quality/proekty-mq-i-winline` | 2294 | 1 |
| `proekty/medium-quality/slowslowcow` | `/shows/medium-quality/slowslowcow` | 2286 | 2 |
| `proekty/mezhdu-nami-show` | `/shows/mezhdu-nami-show` | 1639 | 14 |
| `proekty/miniatures` | `/shows/miniatures` | 1655 | 13 |
| `proekty/ne-spat` | `/shows/ne-spat` | 1616 | 14 |
| `proekty/odnazhdyi-v-rossii` | `/shows/odnazhdyi-v-rossii` | 1621 | 28 |
| `proekty/osp-studiya` | `/shows/osp-studiya` | 1645 | 5 |
| `proekty/outside-stand-up` | `/shows/medium-quality/outside-stand-up` | 1732 | 1 |
| `proekty/plohie-pesni` | `/shows/plohie-pesni` | 1635 | 3 |
| `proekty/prozharka-na-tnt` | `/shows/prozharka-na-tnt` | 1617 | 24 |
| `proekty/rassmeshi-komika` | `/shows/rassmeshi-komika` | 1646 | 31 |
| `proekty/smeh-bez-pravil` | `/shows/smeh-bez-pravil` | 1626 | 34 |
| `proekty/smetanatv` | `/shows/smetanatv` | 2299 | 11 |
| `proekty/smex-v-bolshom-gorode` | `/shows/smex-v-bolshom-gorode` | 1641 | 3 |
| `proekty/standup` | `/shows/standup` | 1637 | 101 |
| `proekty/standup-history` | `/shows/standup-history` | 1650 | 1 |
| `proekty/standup-underground` | `/shows/standup-underground` | 1640 | 33 |
| `proekty/standupclub1` | `/shows/standupclub1` | 1631 | 70 |
| `proekty/standupwomen` | `/shows/standupwomen` | 1624 | 65 |
| `proekty/stendap-ruletka` | `/shows/stendap-ruletka` | 3284 | 23 |
| `proekty/studiya-soyuz` | `/shows/studiya-soyuz` | 1638 | 2 |
| `proekty/superliga` | `/shows/superliga` | 1652 | 8 |
| `proekty/ubojnaya-liga` | `/shows/ubojnaya-liga` | 1628 | 20 |
| `proekty/ubojnoj-nochi` | `/shows/ubojnoj-nochi` | 1620 | 9 |
| `proekty/ubojnyij-vecher` | `/shows/ubojnyij-vecher` | 1623 | 4 |
| `proekty/uralskie-pelmeni-show` | `/shows/uralskie-pelmeni-show` | 1643 | 18 |
| `proekty/zvezdy-ntv/team/zhenshchiny` | `/shows/zvezdy-ntv/teams/zhenshchiny` | 3657 | 4 |

## Проверки предложения

- Span plan получен реальным HTMLParser + link_key/URL_BUILDERS без изменения исходных данных;102keys/782anchors/548fields/422docs/9hidden,unsupported0, все source/targets published.
- R13j опубликован отдельным `5ab9154`; [GitHub CI39914279710](https://github.com/AMnEPka/humorpedia/actions/runs/39914279710) completed/success на точном SHA, все5jobs и3browser-сценария success.
- Root проверил все548 field preimages/782 slices с Unicode codepoint offsets, отсутствие пересечений и сохранение query/fragment; source/plan SHA совпали. На raw projected docs дополнительно проверены99 target UUID/old_id/status и разделение KVN/show teams.
- Независимый read-only review:102 unique keys/99 targets, точные MODX URI/ID и published/not-deleted, все782 spans/548fields/422docs,9 hidden spans в4 полях. Оба override, историческое имя команды и festival-exclusion подтверждены; blockers0. В evidence исправлена опечатка reviewer UUID b14c→b14b по raw snapshot, сама target mapping не менялась. Review `.cache/r13k/mapping-review.json`, SHA256 `e9a90f397b3a0e64035a9b75472119ed9ce63b63c231a05398f106ecb7b29718`; исторические выдержки `.cache/r13k/historical-target-evidence.json`.
- Документация: JSON parse/count checks и113 локальных ссылок PASS; product diff после R13j пуст. План/таблица и обновления статусов включаются в разрешённый отдельный коммит R13k.
- Финальный read-only контроль: clean main `ca46155a9640d4723c07b9fd1762a6e639563414`, прежние container IDs/StartedAt, restarts0, Mongo healthy, HTTP3000 и8001/api/health200.
- Согласование102 mappings получено23.10.2026; новая копия `.cache/r13k/copy/patched.jsonl`, SHA256 `2512f09db268aa68fa59248dca8c8078ab4f33084ce0f4f6edadfaa5464df678`.5 guard tests PASS. Независимая сверка всех25,620 records: ровно422 docs/548fields/782href изменены, остальные25,198 строк побайтно идентичны; все прочие поля/typed IDs/HTML вне spans сохранены. Source SHA не изменился.
- Реальный resolver:2406 unique keys/30831 occurrences,2259 resolved/147 unresolved; relation findings0.122 canonical seasons и9276 participations совпали:missing/stale/changed/duplicate0. Native API/HTTP/browser и cleanup завершены, см. приёмку ниже.

## Приёмка23.10.2026

Все6 шагов согласованного плана выполнены. HEAD до незакоммиченных изменений `5ab9154c14f475ef06fe8aa3ec34aaa786e52821`; branch `codex/local-page-builder`, тот же worktree. Код backend/frontend не изменялся.

- **Копия и guards:** `py -3.14 .cache/r13k/test-prepare-copy.py` —5 PASS. Копировщик R13j сохранён без изменения алгоритма; закреплены новые source/plan SHA и counts. Подготовка: `py -3.14 .cache/r13k/prepare-copy.py --source .cache/r13j/copy/patched.jsonl --plan .cache/r13k/exact-href-plan.json --output-dir .cache/r13k/copy`. Выполнены102keys/782href/548fields/422docs,9 hidden href в4полях; insert/delete0. Новый output создаётся эксклюзивно, исходник не перезаписывается.
- **Независимая сверка:**25,620 records/typed IDs/order сохранены;25,198 неизменённых строк побайтно identical. Отдельный алгоритм reverse-spans восстановил все исходные records, затем сравнил их полностью. Любой HTML byte вне согласованных href, прочие поля, R13i identity corrections и R13h media references сохранены. Скрипт не использует apply helper как oracle. Source SHA не изменился.
- **Реальный resolver и связи:** network-none/read-only audit дал2406unique keys/30831occurrences,2259resolved/147unresolved. Остаток равен прежнему набору249 минус102; festival→news не подставлен. Relation findings0;122 canonical seasons и9276 participations совпали, missing/stale/changed/duplicate0.147 unresolved — результат resolver, не число HTTP404.
- **Native API/HTML:** финальный run `19e128a31ad94b4791c58e1d605b5fcc`, реальный release app/lifespan и Nginx, отдельная UUID Mongo8.0.32/internal network без host ports. Snapshot и media mounts read-only; serving только внутри пилота,indexing=false.422/422 source API/HTML200/noindex,99/99 unique targets API/HTML200/noindex и published. Обычный API содержит ожидаемые canonical href; продуктовые маршруты и ответы не подменялись.
- **Browser:**15 сценариев с реальными кликами:6 типов исходных страниц и9 выбранных случаев — команда Владивостока, Ижица в Лиге Городов, исторические имена, вложенные shows, show teams и typo-prefix. Все15 target h1 точно совпали с ожидаемым названием, а не только с его началом. Проверены обычная вкладка и сохранённый target=_blank; pageerrors0. Выборка использует видимые ссылки и сохраняет подписи. Generic shows переход может использовать существующий breadcrumb на ту же цель; это не утверждение о клике по каждому исправленному span. Визуально выборочно просмотрены source Сборная СПб и target Ижица; полная UX/mobile/accessibility приёмка не выполнялась.
- **Hidden и неизменность после запросов:**9 spans проверены offline, API — expected target sets на родительских страницах; не заявляется проверка каждого hidden response field. Скрытые модули не включались публично. Test-only routes проверили все25,620 seeded records до/после API/browser, допуская только штатные views; остальные поля идентичны. Сохранены ограничения projected copy R13i без roster_import; полный release archive не готовился.
- **Cleanup и основной стенд:** native writers штатно остановлены, UUID DB удалена по marker и отсутствие DB проверено отдельным клиентом. Containers=[],error=null,network и оба owned images удалены; Docker не нашёл оставшихся ресурсов с R13k label. Main clean `ca46155a9640d4723c07b9fd1762a6e639563414`, прежние container IDs/StartedAt,restarts0,Mongo healthy,HTTP3000 и8001/api/health200. Импорт24СМИ и VPS не затронуты.

Финальная копия `.cache/r13k/copy/patched.jsonl`, SHA256 `2512f09db268aa68fa59248dca8c8078ab4f33084ce0f4f6edadfaa5464df678`. Source R13j SHA256 `90e38c00f870bcbf28702675097eb752b8304148f5556d61d481e8985f9e4ea7` неизменен.

Evidence: `.cache/r13k/acceptance-final.json`, `copy/{acceptance,pages}.json`, `audits/{summary,content-audit,relations-audit}.json`, `independent-copy-audit.{py,json}`, `native-pages/19e128a31ad94b4791c58e1d605b5fcc/{result,cleanup,commands}.json`, `closed/links-{http,browser}.json` и screenshots. Raw data/logs/media остаются ignored и в Git не добавляются.

Полный backend/сборка frontend/CI в R13k повторно не запускались: продуктовый код не менялся. Сохранены R13j evidence1200 backend passed/16skipped и GitHub39914279710 success на5ab9154 (5jobs/3browser-сценария), frontend build R13f release `340fa99dc58ed63e53a92bd50009ba386b1ec5f9dcf80af25cccdddec5506a7b`. Это прежние результаты, не новые прогоны R13k.

## Уточнения browser checker

Первые два run `73f309d03d5d40e1845f0b0e17bd6b82` и `88a15864cf8246cc9a9e52e93d5fa658` прошли API/HTML422+99, но browser сначала выбрал hidden mobile teaser перед видимой bio link, затем ожидал same-tab navigation у сохранённого target=_blank. Исправлен только checker: visible anchor и настоящий popup. Cleanup обоих успешен; это не browser success.

Run `40b758e9618046a6b9b1ed8a6e45af86` прошёл15кликов и after snapshot, но root при проверке evidence заметил, что substring-проверка принимала ещё не обновившийся заголовок «Money Mic (2-й сезон)» для цели «Money Mic». Условие заменено точным равенством; финальный 19e128a31ad94b4791c58e1d605b5fcc подтвердил все15 названий. Snapshot и код приложения между попытками одинаковы; API/backend scope не расширялся. Все4cleanup успешны. Это исправления измерения, не изменение пользовательского поведения.

Независимый final scope review `.cache/r13k/final-scope-review.json`, SHA256 `83b0ab0865ab1dcb64fb84ae743c8edd10bc3e1456a8bdccd40ca48a2d617cd4`: свежий run19e128 проверен по артефактам, blockers0. Подтверждены exact headings, popup, snapshot до/после и cleanup; граница breadcrumb/hidden coverage отражена выше.

## Доставка и остаток

Пользователь разрешил отдельный commit/push R13k с документацией. В тот же пакет входят накопленные обновления статусов публикации R13j/CI. Основной стенд не переключать, на VPS не выкладывать.

Остаток147 keys, включая festival KiViN-2024, требует отдельного точного review; общий slug fallback запрещён прежними решениями. Поиск8 оригинальных season posters,111external/embed URL, применение согласованной demo-policy к полноценному release archive, интеграция и dev-sync после интеграции остаются отдельными этапами. Новые изменения данных сверх102 mappings не выполнялись.

## Публикация и продолжение23.10.2026

R13k и документация опубликованы отдельным `8ddd3964633700be03e4a1245ab3cfc79d18b1a8`, push в `origin/codex/local-page-builder`. [GitHub39926764123](https://github.com/AMnEPka/humorpedia/actions/runs/39926764123) completed/success,attempt1 на точном SHA: все5jobs и3browser-сценария success. Evidence `.cache/r13l/r13k-ci-{run,jobs}-final.json`.

Продолжение [R13l](r13l-reviewed-link-plan-2026-10-23.md) согласовано и принято на изолированной копии:75правил/73keys/319href/247fields/205docs,hidden10;69published targets+2существующих каталога. API/HTML205+69+2 и browser21 PASS,unresolved74. Исходник R13k неизменен; R13l не закоммичен. Main/24СМИ/VPS unchanged.
