# R13p — шесть старых href на существующие города и команду

> Согласовано пользователем24.10.2026: шесть точных замен на новой изолированной копии. Реализовано и проверено в текущем worktree; коммит R13p ещё не выполнялся.

**Дата:**24.10.2026. **Статус:** реализация и изолированная приёмка PASS. Copy R13o сохранена; новая copy R13p содержит только6согласованных href edits.

**Цель:** восстановить шесть кликабельных ссылок в пяти новых страницах R13o, направив их на шесть существующих published целей без изменения подписей и остальных данных.

**Архитектура:** guarded offline преобразование новой JSONL-копии; только exact href value spans внутри пяти modules[0].data.content. Никаких alias additions, глобального slug fallback или runtime-кода.

**Стек:** существующий Python/FastAPI/Mongo/React; offline resolver на SnapshotDB, native API/SPA/React на собственной UUID Mongo/internal network; новых зависимостей нет.

Worktree `r5-zip-operations/humorpedia`, ветка `codex/local-page-builder`, HEAD до новых документов `f1a37c75d742869ccdebb2da2ee3f5ec9396ce18`. R13o опубликован этим SHA; [GitHub40065160349](https://github.com/AMnEPka/humorpedia/actions/runs/40065160349) completed/success:5jobs/3browser-сценария. Точный scope, ID, spans и hashes — в [JSON](r13p-relative-href-plan-2026-10-24.json).

## Обоснование и варианты

R13o намеренно сохранил6исходных относительных href; actual resolver сейчас показывает подписи текстом. После публикации выполнено read-only исследование источника и существующих целей. Все6целей уже есть в принятой copy, их SQL old_id/URI и current document ID сопоставлены. Создавать страницы и добавлять aliases не требуется.

Рекомендуемый вариант — заменить только шесть значений href по точной таблице ниже. Альтернативы: оставить текущий текстовый показ либо отдельно проектировать legacy aliases; последнее расширяет маршрутизацию и не нужно для этих6контекстов. Отдельное согласование R13p получено24.10.2026; прежнее правило R13o «сохранить href» изменено только для этих6точных позиций.

## Точная таблица

| Страница-источник old_id | Подпись без изменений | Исходный href | Предлагаемый target | SQL old_id цели |
|---|---|---|---|---:|
|1585|Краснодар|`krasnodar.html`|`/city/krasnodar`|2092|
|1587|Воронеж|`voronezh.html`|`/city/voronezh`|2072|
|1588|Хабаровск|`khabarovsk.html`|`/city/khabarovsk`|2111|
|1590|Красноярск|`krasnoyarsk.html`|`/city/krasnoyarsk`|2079|
|1590|Не в форме|`ne-v-forme.html`|`/kvn/teams/ne-v-forme`|1427|
|1592|Челябинск|`chelyabinsk.html`|`/city/chelyabinsk`|2090|

Это5полей5документов: Краснодарская1585,Старт1587,Тихоокеанская1588,Азия1590(2ссылки в одном поле),Уральская1592. Все source/target страницы published на текущей копии. Никаких замен по одному совпадению названия или alias.

## Доказательства идентичности

Независимый review `.cache/r13p/identity-review.json`: пять городов и одна команда подтверждены SQL table/ID/URI и strict совпадением current old_id. Дополнительно source metadata проверены прямо в immutable `humorbd.sql`, SHA256 `d4a2e0930ebc676aca939ad569c54bc82e7470184ca0c40ede63e9a19898cf19`; pure parser индексировал3374resources,6точных metadata matches. SQL/старый сайт не исполнялись.

**Красноярск:** в SQL alias krasnoyarsk принадлежит и городу2079 `city/krasnoyarsk.html`, и команде2004 `zvezdy-ntv/team/krasnoyarsk.html`. В исходнике Азии ссылка находится в поле «Город проведения», подпись «Красноярск»; current city document old_id2079. Предложена именно `/city/krasnoyarsk`, команда2004 исключена. Глобальной связи alias→город не создаётся.

**«Не в форме»:** SQL1427 `kvn/team/ne-v-forme.html`, current teams old_id1427, team_type=kvn и без show_id; actual team_url даёт `/kvn/teams/ne-v-forme`. Исходный контекст — строка команды за2023год, а не город или команда другого шоу.

Actual `resolve_targets` выполнен offline с SnapshotDB:6исходных keys не разрешаются; все6канонических target keys разрешаются ровно в заявленные URL. Проверены actual URL_BUILDERS `/city/{slug}` и KVN team_url, current target ID/status. Это не HTTP/UI-приёмка будущей правки.

## Контракт изменения и предусловия

Source `.cache/r13o/copy/patched.jsonl`:25,630records, SHA256 `7834b90269e613ed9d30c851eeb7f71aa692878a419d8d018054af739595f7b3`. Для каждого поля pinned source UTF-8 SHA256, каждого href — character offsets/preimage; для будущего поля вычислен ожидаемый output SHA256. Для целей pinned raw row SHA/typed ID/old_id/status/canonical. Все перечислены в JSON.

Меняются только6значений атрибута href; кавычки, target/rel/прочие атрибуты, текст/HTML-разметка/заголовки/таблицы/теги и порядок сохраняются. Нельзя извлекать content заново из SQL: источник уже содержит6принятых удалений inline-рекламы R13o. Повторное внесение рекламы запрещено.

Будущая copy остаётся25,630records:0insert/0delete,5changed docs/fields,25,625original raw rows byte-identical. Все parent.child_kvn_ids, UUID/old_id/status/old_urls, Лампа, другие R13h–o исправления,122canonical seasons/5tournaments/9276participations неизменны. Source copy immutable, output exclusive; drift/duplicate/reapply/неоднозначный target — остановка.

Прогноз resolver:61−6=**55unresolved keys** и точный old-residual-set минус эти6keys. Это прогноз; future actual resolver должен подтвердить его на новой copy до приёмки. Непредусмотренные новые/исчезнувшие keys требуют разбора без автоматического расширения пакета.

## Границы

Только новая изолированная copy. Main checkout/стенд/DB/media, импорт24СМИ, VPS, индексирование, Mongo topology, full export-local/dev-sync не затрагиваются. Не создаются остальные28 legacy resources/родитель2536/сезоны, не ищутся/не заменяются media/posters. KVN server HTML/301 — отдельная задача; действует принятый SPA-контракт.

## Согласованный план

| Задача | Файлы и действия | Проверка готовности | Модель |
|---|---|---|---|
|1. Guarded patch | `.cache/r13p/prepare-copy.py`, `test-prepare-copy.py`; exact6href value spans в5fields, без общей HTML-нормализации | RED→GREEN: source/field/target identity/status drift, wrong span/duplicate/reapply/existing output fail; два запуска byte-identical; non-string BSON IDs сохраняются | Sol/high |
|2. Новая copy | `.cache/r13p/copy/patched.jsonl`, exact href/provenance/acceptance |25,630rows/5changed/0insert/0delete,25,625rawrows unchanged;6edits;source/output field hashes; all other fields equal | Sol/high |
|3. Независимый offline audit | `.cache/r13p/audits/`, actual resolver/model/relation checks без app/Mongo |55exact residual-set,0collisions/relations;122/5/9276 unchanged;6targets и остальные данные byte/field-identical;R13o12blocks/23tables/167tags без возврата рекламы | Luna/high |
|4. Native API/SPA/React | `.cache/r13p/harness/`, `run-native.cjs`, `check-links.cjs`; owned UUID Mongo/internalnetwork/nohostports/source-mediaRO; тот же frontend release |5source+6target API/SPA200/noindex по текущему контракту;6реальных exact authored link clicks с ожидаемыми target headings,0pageerrors; подписи/атрибуты сохранены;25,630non-view before/after fields equal | Sol/high |
|5. Cleanup/report | Только owned DB/containers/network/images; read-only main status/health; task MD/JSON |source unchanged,2fixture-only source-verified navigation id overlays явно учтены;cleanup PASS;main branch/IDs/starts/restarts unchanged;commit/push только по поручению | Sol/high |

Native fixture может использовать те же2source-verified id overlays parent1503/root32, что R13o, только в seed/expected fixture. Это не изменение source copy и не full DB/index readiness; прежний projection caveat unique kvn.id/null фиксируется отдельно. Входящий browser click обязан попасть в exact authored anchor внутри правильного source field; ждать expected heading после React route, не только URL/любой h1.

## Исходное read-only исследование

Read-only:6source href spans/5fields,6sourceSQL identities и current target rows доказаны; actual resolver12keys проверен offline `--network none`, без приложения/DB; поля proposed-output hashes рассчитаны в памяти. Новой copy/изменённых JSONL-документов не создавалось, данные не применялись. При подготовке metadata builder учтён BSON ObjectId для чужих строк: они не превращаются в string IDs и не нормализуются.

Evidence `.cache/r13p/identity-review.json`, `source-href-spans.json`, `direct-sql-verification.json`, `target-resolver-readiness.json`; SQL/полная copy/сырые журналы в Git не добавляются.

**Согласовано:** пользователь подтвердил6точных замен в5документах на новой копии24.10.2026. Независимый proposal review PASS_WITHOUT_APPLY сохранён до реализации; теперь приёмка результата приведена ниже.


## Приёмка R13p —24.10.2026

HEAD до незакоммиченных изменений: `f1a37c75d742869ccdebb2da2ee3f5ec9396ce18`, ветка `codex/local-page-builder`. R13o уже опубликован и GitHub CI успешен; R13p пока не коммитился/не публиковался. Продуктовые файлы не менялись.

1. Guarded converter:9tests RED→GREEN. Проверены source/plan/field/target identity/status/raw hash drift, неверные/дублированные spans, повторное применение, существующий output, сохранность typed BSON IDs. Frozen apply-plan SHA `7a5d027e2cc85455033f783ec1d280181a65a0b54c9b7e32bdb9a5e457c97977`.
2. Новая copy `.cache/r13p/copy/patched.jsonl`, SHA `44d72ff221401637ebaf561a97d3ec019903b66faf5ba8fff13a51ed63b33993`. Повтор в отдельный exclusive output дал идентичный SHA.25,630records,6href values/5fields/5docs,0insert/0delete,25,625raw rows byte-identical. Прочие значения изменённых документов, все target rows, parent.child_kvn_ids/aliases/status/media и канонические коллекции сохранены.
3. Независимый structural + actual offline resolver/model/relation audit PASS: **61→55unresolved**, точный residual-set минус6согласованных keys;0canonical collisions/old_url conflicts/relation findings.9KVN models valid;122seasons/5tournaments/9276participations без изменений. R13o:9pages/12blocks/23tables/167tags/121href attrs,0inline ad snippets; HTML58,097→58,108chars ровно на11символов разницы новых URL.
4. Native run `e8798e724037433a8c08d65fd9a8451b`:5source+6target API/SPA200/noindex; **6реальных кликов** по exact authored anchors в `.prose` с сохранением подписей/атрибутов и ожиданием правильного target h1,0pageerrors. Красноярск открыл город2079; «Не в форме» — команду1427. Before/after всех25,630records: non-view domain fields неизменны. Скриншоты всех6source/6target сохранены; вручную просмотрены Красноярск и «Не в форме».
5. Cleanup PASS: native backend штатно завершён, owned DB отсутствует, UUID containers/network/images удалены. Основной checkout чистый `main@ca46155a9640d4723c07b9fd1762a6e639563414`;3container IDs/StartedAt/restarts совпали с baseline, frontend3000 и API8001health вернули200.24СМИ/VPS не затрагивались.

Использован тот же frontend release `1bc6820bb6cc2e3c0099106d7b1aed96ece05e21dbe6c736571c7115ba2378d6`; повторной сборки frontend для data-only пакета нет. Native fixture использует прежние2source-verified parent/root ID overlays только при seed/проверке. Сохраняется известное startup-предупреждение unique kvn.id/null на прочих projection rows: полная DB/index readiness не заявляется. Исходная JSONL copy эти overlays не получает. KVN server HTML/301,55остальных неразрешённых keys,8постеров и индексирование не входят в этот пакет.

Первый offline runtime запуск аудита остановился в проверочном коде при JSON-сериализации BSON ObjectId. Исправлено только разделение structural canonical JSON и отдельного BSON decode для runtime; повторный structural/offline audit PASS. Преобразователь и обе copy не менялись; native приёмка прошла с первого запуска.

Локальные команды (из этого worktree; output обязан быть новым):

```powershell
py -3.14 .cache/r13p/test-prepare-copy.py
py -3.14 .cache/r13p/prepare-copy.py --source .cache/r13o/copy/patched.jsonl --plan .cache/r13p/apply-plan.json --output .cache/r13p/copy-new
py -3.14 .cache/r13p/independent-copy-audit.py
$env:BROWSER_BUILD_DIR=(Resolve-Path .cache/r13n/frontend-build).Path
node .cache/r13p/run-native.cjs
node .cache/r13p/check-main.cjs
```

Actual resolver/model/relation выполнялись в `humorpedia-r12b-backend-dev` с `--network none`, `/work` read-only и собственным `/out`; script `independent-copy-audit.py --root /work --runtime --output /out/offline-runtime-audit.json`. Игнорируемые audit/native/provenance artifacts и их SHA перечислены в task JSON; dump/полная copy/сырые журналы не добавляются в Git. Для последующей интеграции использовать ровно согласованные mappings/spans и pinned source; полный dev-sync/перенос данных отдельно.

Финальный независимый scope/acceptance review R13p: **PASS,0blocking findings**, `.cache/r13p/final-scope-review.json`. Повторно сверены raw delta/шесть spans/5fields/5docs, все source/final/repeat SHA и native/offline evidence; границы projection/fixture/SPA явно сохранены. Все5задач согласованного плана завершены.

## Публикация24.10.2026

Пользователь поручил отдельный commit/push R13p с документацией и проверку GitHub CI. Приёмка выше относится к неизменённой accepted copy; source/final SHA и23evidence hashes повторно проверены перед публикацией. Назначение: `origin`, точный ref `refs/heads/codex/local-page-builder`; main/24СМИ/VPS не затрагиваются.
