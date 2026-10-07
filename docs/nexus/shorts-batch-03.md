# Шортсы Nexus — пачка №3: познавательные + воронка на панель

Генерация как раньше: Krea → Video, текст → видео, 5 с, **9:16**, звук выключен.
Файлы: `e<ролик>_<сцена>.mp4` (познавательные) и `p<ролик>_<сцена>.mp4` (панель) → `/opt/video-mcp/data/videos/nexus/`.

**Надписи на экране.** Колонка «Надпись» — это крупный текст сверху кадра, его ставит сервер (по-русски, ровно).
В промптах нейросети букв нет: русские буквы она пишет криво. Исключение — короткие латинские слова
(DPI, VPN, SNI): их можно попросить нарисовать прямо в кадре, см. «Рисованные надписи» в конце.

СТИЛЬ (вписан в каждый промпт): `vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents,
high contrast, smooth camera, no text, no letters, no logos`

---

## e1 · «Пинг важнее скорости» (~25 с)

| # | Голос | Надпись | Промпт для видео |
|---|---|---|---|
| 01 | Скорость по тесту 100 мегабит, а игра лагает и звонки рвутся. Дело не в скорости. | 100 МБИТ — И ЛАГИ? | `frustrated gamer in a dark room lit by a monitor, headphones on, frozen game glow on his face; slow push-in; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 02 | Скорость — это ширина трубы. А пинг — сколько времени сигнал идёт туда и обратно. | ПИНГ | `a single glowing light pulse traveling along a long neon cable to a distant server and bouncing back; the pulse moves there and back; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 03 | Для видео важна ширина. Для игр и звонков — именно пинг. | ШИРИНА ≠ ЗАДЕРЖКА | `two neon pipes side by side, one very wide with slow light, one thin with very fast light pulses; camera moves along the pipes; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 04 | Чем дальше сервер и чем больше по пути проверок, тем выше пинг. | ДАЛЬШЕ = ДОЛЬШЕ | `a light pulse passing through several glowing checkpoint gates over a long distance, slowing at each gate; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 05 | Поэтому сервер поближе часто важнее, чем «самый быстрый тариф». | | `a glowing server tower very close to a bright city, short bright light bridge between them; slow orbit; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 06 | — | карточка VPN | `endcard-vpn` |

## e2 · «Что такое VPN — за 30 секунд» (~28 с)

| # | Голос | Надпись | Промпт для видео |
|---|---|---|---|
| 01 | VPN — это не «приложение для блокировок». Это туннель. | VPN = ТУННЕЛЬ | `a glowing neon tunnel opening in a dark digital space, camera flies into it; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 02 | Без него твой трафик идёт открыто: провайдер видит, куда ты ходишь. | | `transparent glass pipes with visible glowing packets moving inside, an observer silhouette watching; slow pan; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 03 | С VPN всё упаковано в шифрованный туннель до сервера в другом месте. | ШИФРОВАНИЕ | `glowing packets entering an opaque armored neon tube and disappearing from view; steady flow; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 04 | Сайты видят адрес сервера, а не твой. Провайдер видит только, что ты подключён к VPN. | | `a masked glowing figure stepping out of a tunnel exit in a distant city; slow cinematic reveal; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 05 | А вот само подключение к VPN оператор как раз и пытается узнать и заблокировать. Об этом — в других роликах. | | `a scanner beam sweeping over the armored neon tube, red warning glow appearing; tense slow push-in; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 06 | — | карточка VPN | `endcard-vpn` |

## e3 · «Почему сайт открывается, а видео на нём — нет» (~26 с)

| # | Голос | Надпись | Промпт для видео |
|---|---|---|---|
| 01 | Страница грузится мгновенно, а видео крутится бесконечно. Знакомо? | | `a phone screen with an endless loading spinner glowing in a dark kitchen at night; slow push-in; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 02 | Это не обязательно блокировка. Часто это замедление. | ЗАМЕДЛЕНИЕ | `a bright stream of light suddenly squeezed into a thin trickle by glowing clamps; slow motion; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 03 | Текст весит мало и проходит. А видео — тяжёлое, его режут в первую очередь. | ТЕКСТ ✓ ВИДЕО ✗ | `small light particles passing freely through a filter while large glowing blocks get stuck in it; steady motion; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 04 | Оборудование узнаёт сервис и просто ограничивает ему скорость. | | `a black network appliance with blinking lights, a cyan stream entering wide and leaving thin; slow pan; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 05 | Поэтому и кажется, что «интернет есть, но какой-то не такой». | | `person on a sofa staring at a phone in disbelief, warm lamp and neon window light; gentle push-in; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 06 | — | карточка VPN | `endcard-vpn` |

---

## Воронка на панель (для владельцев VPN-сервисов)

Эти ролики смотрят меньше людей, но каждый зритель — потенциальный клиент на 3 990–5 490 ₽/мес.
В конце — **карточка панели** (`docs/nexus/brand/endcard-panel.png`: «Панель Nexus · @Nexus_dev · от 3 990 ₽»).
Лучше всего продаёт **настоящая запись экрана панели** (демо-панель с выдуманными юзерами): где она есть в
таблице — это не нейросеть, а запись 5–8 секунд с телефона или OBS.

## p1 · «5 вещей, которые съедят ночи владельца VPN» (~30 с)

| # | Голос | Надпись | Кадр |
|---|---|---|---|
| 01 | Держишь свой VPN? Вот что съест твои ночи. | СВОЙ VPN? | `exhausted young admin at 3 am in front of glowing monitors, energy drink cans on the desk; slow push-in; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 02 | Раз — сервер забанили, а ты узнал от клиентов. | 1. БАН НОДЫ | `a phone flooding with notifications on a dark desk; rapid flashing; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 03 | Два — оплаты и продления руками. Три — один ключ на десятерых. | 2. ОПЛАТЫ · 3. ШАРИНГ | `one glowing key being copied into many identical keys floating in the air; slow multiplying motion; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 04 | Четыре — белые списки, когда у всех лежит. Пять — переезд с другой панели и потерянные клиенты. | 4. БЕЛЫЕ СПИСКИ · 5. ПЕРЕЕЗД | `a glowing gate closing in a dark digital city while light streams crash into it; dramatic slow motion; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 05 | Я закрыл всё это в своей панели. Она уже работает на 13 проектах. | | **запись экрана демо-панели:** главный экран, список нод |
| 06 | — | карточка панели | `endcard-panel` |

## p2 · «Ноду забанили в 3 ночи — клиенты не заметили» (~27 с)

| # | Голос | Надпись | Кадр |
|---|---|---|---|
| 01 | Три часа ночи. Сервер улетел в бан. | 03:00 | `a server rack in a dark data center, one module's light turns from green to red; slow push-in; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 02 | Панель видит это сама — проверки идут из российских сетей. | | **запись экрана:** центр состояния / мониторинг с находкой |
| 03 | Через API хостинга поднимает новый сервер и переносит на него клиентов. | АВТОЗАМЕНА | `a robotic arm replacing a dark server module with a bright glowing one; precise motion; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 04 | А тебе в Телеграм приходит одно сообщение: что было и что уже сделано. | | **запись экрана:** алерт в админ-боте |
| 05 | Ты спишь. Клиенты не замечают. Панель Nexus. | | `a person peacefully sleeping, a phone on the nightstand glowing softly green; slow pull-back; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 06 | — | карточка панели | `endcard-panel` |

## p3 · «Переехал с Marzban за вечер — без потери клиентов» (~25 с)

| # | Голос | Надпись | Кадр |
|---|---|---|---|
| 01 | Переезд на другую панель — это страх потерять клиентов. | ПЕРЕЕЗД = РИСК? | `a glowing bridge between two neon platforms with small light figures walking across; slow pan; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 02 | В Nexus загружаешь бэкап старой панели — Marzban, Remnawave, 3x-ui, Hiddify. | REMNAWAVE · MARZBAN · 3X-UI | **запись экрана:** раздел импорта |
| 03 | Панель показывает, что нашла, и переносит клиентов с их сроками. | | **запись экрана:** результат разбора бэкапа |
| 04 | Клиенты продолжают пользоваться, а у тебя — тарифы, оплаты, мониторинг и режим для белых списков. | | `light figures arriving at a bright new platform and lighting it up; uplifting slow motion; vertical 9:16, cinematic, dark navy background with cyan and magenta neon accents, high contrast, smooth camera, no text, no letters, no logos` |
| 05 | — | карточка панели | `endcard-panel` |

---

## Рисованные надписи прямо в кадре (по желанию)

Nano Banana (картинки) хорошо пишет **короткие латинские слова**. Если хочется, чтобы надпись была частью
кадра (на мониторе, на табличке, неоном на стене), — делать **картинку в Nano Banana → оживить в видео**
(картинка → видео: буквы держатся стабильнее). Пример:

`a glowing neon sign on a dark brick wall that reads "DPI" in bold cyan letters, rain reflections on the ground,
vertical 9:16, cinematic, dark navy and magenta neon`

Работает для: DPI, VPN, SNI, CDN, PING, 404, ERROR. Русские слова так не делать — ставим их надписью сверху.

Порядок выхода: s2 → c4 → e1 → s3 → **p1** → c2 → e2 → s4 → c3 → **p2** → e3 → s5 → c5 → **p3**.
