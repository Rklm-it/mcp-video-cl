# Шортсы Nexus — пачка №1 (5 роликов, задание для генерации)

Как делать:
1. **Картинка** каждой сцены: Krea → Image → модель **Nano Banana**, формат **9:16**, промпт из поля «Картинка».
   К каждому промпту в конце добавить СТИЛЬ (ниже). Сделать 2–3 варианта, оставить лучший.
2. **Видео** из картинки: Krea → Video (Kling / Seedance / Veo — что лучше выходит), image-to-video, **5 секунд,
   9:16**, промпт из поля «Движение». Если видео вышло плохо — оставить картинку, я её анимирую сам.
3. Назвать файлы `s<ролик>_<сцена>`: `s1_01.mp4`, `s1_02.png`… и положить на tubgw в
   `/opt/video-mcp/data/videos/nexus/`. Голос, субтитры, музыку и концовку добавлю я.

**Текста и букв в кадре быть не должно** — субтитры ставит сервер, а нейросети пишут буквы криво.

**СТИЛЬ (добавлять к каждой картинке):**
`vertical 9:16, cinematic, dark navy background, cyan and magenta neon accents, high contrast, shallow depth of
field, clean minimal composition, no text, no letters, no logos`

---

## s1 · «Как сервисы живут при белых списках» (~28 с)

| # | Голос | Картинка | Движение |
|---|---|---|---|
| 01 | Белые списки включили — а у некоторых VPN всё работает. Как? | young man in a dark room holding a glowing smartphone, surprised face lit by the screen, rain on the window behind | slow push-in to the face, raindrops slide down the window |
| 02 | При белом списке оператор пропускает только разрешённые адреса: банки, Госуслуги, крупные облака. | a massive glowing gate in a dark digital city, only a few bright streams of light pass through, the rest crash into it | light streams fly toward the gate, most of them shatter into sparks |
| 03 | Значит, нужно, чтобы трафик шёл к адресу из списка. | a single cyan light stream curving around and entering the gate through a bright opening | the stream bends smoothly and passes through the opening |
| 04 | Для этого вход в сервис прячут за облаками и CDN — сетями серверов крупных компаний. | huge server halls seen from above like a glowing city grid, cyan light flowing between buildings | slow aerial drone flight over the server grid |
| 05 | Оператор видит разрешённый адрес и пропускает. Но такие входы тоже регулярно закрывают — гонка не кончается. | a hand-drawn-style neon chessboard with glowing pieces, one piece moving forward | a chess piece slides one square, light pulses across the board |
| 06 | Как админы успевают за этой гонкой — дальше на канале. Подписывайся на Nexus. | system administrator at night in front of two monitors with graphs, city lights outside | gentle camera pull-back, monitor glow flickers |

## s2 · «VPN работает дома, но не на мобильном» (~27 с)

| # | Голос | Картинка | Движение |
|---|---|---|---|
| 01 | Дома VPN летает, вышел на улицу — тишина. Это не глюк телефона. | split scene: cozy apartment with warm light on one side, cold rainy street on the other, the same phone in both | camera pans from the warm room to the cold street |
| 02 | Домашний интернет и мобильный — это разные сети с разными фильтрами. | two glowing network tunnels side by side, one wide and calm, one narrow with red barriers | light flows freely in the wide tunnel and stutters in the narrow one |
| 03 | У мобильных операторов фильтры часто строже: режут целые подсети зарубежных хостингов. | a glowing wall with whole blocks of lights switching off at once | rows of lights turn off one block after another |
| 04 | А ещё узнают протоколы по почерку — размеру и ритму пакетов. | abstract neon waveforms being scanned by a horizontal laser line | the laser line sweeps down across the waveforms |
| 05 | Поэтому нормальный сервис держит несколько протоколов и подключений — на случай, если один задушат. | several parallel neon cables, one goes dark while the others stay bright | one cable fades out, light jumps to the neighboring cable |
| 06 | Как это настроить без бессонных ночей — расскажу дальше. Подписывайся на Nexus. | a calm person sleeping, a laptop on the desk glows with a green status light | slow push-in to the green status light |

## s3 · «Почему у МТС работает, а у Билайна нет» (~26 с)

| # | Голос | Картинка | Движение |
|---|---|---|---|
| 01 | Один и тот же VPN: у друга на одном операторе работает, у тебя на другом — нет. | two friends on a bench in a Russian courtyard comparing their phones, one smiling, one frustrated, autumn evening | slight handheld camera movement, leaves falling |
| 02 | Оборудование для фильтрации у операторов похожее, а правила и обновления доходят по-разному. | rows of identical black network appliances, some with green lights, some with red | lights on the appliances switch from green to red one by one |
| 03 | Где-то новое правило включили сегодня, а где-то через неделю. И регион тоже решает. | a dark map-like landscape with glowing cities lighting up in red at different moments | red dots appear across the landscape one after another |
| 04 | Поэтому «у меня работает» ничего не значит. Проверять надо у разных операторов и в разных городах. | several smartphones on a table, each with a different colored glow, connected by thin light lines | light lines pulse between the phones |
| 05 | Админы ставят проверки в нескольких сетях и видят проблему раньше, чем пишут клиенты. Подписывайся на Nexus. | administrator looking at a wall of small glowing status tiles, most green, one turning red | one tile turns red, the admin leans forward |

## s4 · «Провайдер видит, куда ты заходишь — даже по https» (~25 с)

| # | Голос | Картинка | Движение |
|---|---|---|---|
| 01 | Думаешь, замок в браузере прячет, на какой сайт ты зашёл? Нет. | a glowing padlock icon made of light floating in darkness, slightly transparent | the padlock slowly turns and becomes see-through |
| 02 | Содержимое зашифровано. Но имя сайта уходит открытым текстом в самом начале соединения. | a sealed glowing envelope with a transparent label on the outside | camera moves closer to the transparent label |
| 03 | Это поле называется SNI. Его и читает оборудование оператора. | a scanner beam reading the label of passing envelopes on a conveyor belt | envelopes move along the conveyor, the beam flashes on each |
| 04 | Есть технология, которая прячет и имя, — ECH. Но в России её фильтруют. | an envelope wrapped in a dark cloak, stopped by a red barrier | the cloaked envelope approaches and the red barrier flashes |
| 05 | Поэтому то, что ты видишь замок, ещё не значит, что тебя не видят. Подписывайся на Nexus. | a person in a dark room looking at a phone, a faint silhouette of an eye in the reflection on the window | slow push-in, the reflection becomes slightly clearer |

## s5 · «Как узнать, что сервер упал, раньше клиентов» (~27 с)

| # | Голос | Картинка | Движение |
|---|---|---|---|
| 01 | Три часа ночи. Сервер лёг. Узнаешь об этом утром — из гневных сообщений. | a phone on a bedside table at night lighting up again and again with notifications, dark bedroom | the phone vibrates and lights up repeatedly |
| 02 | Проблема в том, что сервер может «жить» для тебя и быть мёртвым для клиентов в России. | a glowing server in a cold foreign data center, a broken light bridge stretching toward a distant city | the light bridge cracks in the middle |
| 03 | Поэтому проверять надо оттуда, где сидят клиенты: из домашних и мобильных сетей. | small glowing sensors placed in apartment windows across a night city | sensors light up one by one across the windows |
| 04 | Нормальный мониторинг сам пишет в Телеграм: что упало, у кого и что делать. | a smartphone on a desk receiving one calm notification with a soft cyan glow | the screen lights up gently, camera pushes in |
| 05 | А лучше — сам поднимает замену. Я так и сделал у себя в панели. Подписывайся на Nexus. | a robotic arm replacing a glowing server module in a rack, smooth and precise | the arm pulls out the dark module and inserts a bright one |

---

Проверено перед записью: белые списки на мобильном пропускают только разрешённые ресурсы; SNI передаётся
открыто в начале TLS-соединения; ECH в России фильтруют (с ноября 2024). Формулировки без обещаний «100% работает».
