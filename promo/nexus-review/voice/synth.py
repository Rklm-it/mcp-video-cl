#!/usr/bin/env python3
"""Озвучка обзора Nexus через ElevenLabs — с бережным расходом кредитов.

Текст берётся из блоков ```voice id=...``` сценария docs/nexus/review-v2.md. Каждый блок озвучивается
отдельно (переделали фразу — переозвучиваем только её часть) и сохраняется с таймингами слов:
по ним монтаж режет сцены и ставит субтитры.

Ключ — из окружения: ELEVENLABS_API_KEY (или REELS_ELEVENLABS_API_KEY, как у фабрики роликов).
В чат и в репозиторий ключ не писать.

    python3 synth.py --count                         # сколько символов в каждом блоке и всего (кредиты не тратит)
    python3 synth.py --credits                       # тариф и остаток кредитов
    python3 synth.py --voices                        # голоса аккаунта (id, имя, язык)
    python3 synth.py --samples ID1 ID2 ID3           # одна фраза разными голосами → out/voice/sample-*.mp3
    python3 synth.py --voice ID --blocks hook,cdn    # озвучить блоки → out/voice/<id>.mp3 + <id>.json
    python3 synth.py --voice ID --blocks all --yes   # весь сценарий (больше лимита — только с --yes)

Перед синтезом скрипт считает символы и сверяет с остатком; больше --max-chars (по умолчанию 1500)
за один запуск без --yes не тратит. eleven_multilingual_v2 стоит 1 кредит за символ.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "docs/nexus/review-v2.md"
OUT = Path(__file__).resolve().parents[1] / "out/voice"
API = "https://api.elevenlabs.io"
MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
SAMPLE_TEXT = ("Белые списки на мобильном интернете: обычный ви-пи-эн просто перестаёт работать. "
               "Нексус прячет ноду за российским си-ди-эн, и трафик проходит.")


def key() -> str:
    k = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("REELS_ELEVENLABS_API_KEY")
    if not k:
        sys.exit("Нет ключа: задайте ELEVENLABS_API_KEY в окружении (настройки среды), не в коде и не в чате.")
    return k


def call(method: str, path: str, body: dict | None = None, timeout: int = 180) -> dict:
    req = urllib.request.Request(
        API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"xi-api-key": key(), "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        # причина отказа — на экран: «нет кредитов», «голос недоступен на бесплатном тарифе» и т.п.
        sys.exit(f"ElevenLabs {e.code}: {e.read().decode(errors='replace')[:500]}")


def blocks() -> dict[str, str]:
    text = SCRIPT.read_text(encoding="utf-8")
    found = re.findall(r"```voice id=(\w+)\n(.*?)```", text, flags=re.S)
    return {bid: " ".join(body.split()) for bid, body in found}


def remaining() -> tuple[int, dict]:
    sub = call("GET", "/v1/user/subscription")
    return sub.get("character_limit", 0) - sub.get("character_count", 0), sub


def guard(chars: int, max_chars: int, yes: bool) -> None:
    left, sub = remaining()
    print(f"Уйдёт ≈{chars} кредитов ({MODEL}), осталось {left} (тариф {sub.get('tier')}).")
    if chars > left:
        sys.exit("Не хватает кредитов — озвучку не запускаю.")
    if chars > max_chars and not yes:
        sys.exit(f"Больше лимита {max_chars} за запуск. Если так и задумано — добавьте --yes.")


def tts(voice: str, text: str, name: str) -> Path:
    data = call("POST", f"/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128",
                {"text": text, "model_id": MODEL})
    OUT.mkdir(parents=True, exist_ok=True)
    mp3 = OUT / f"{name}.mp3"
    mp3.write_bytes(base64.b64decode(data["audio_base64"]))
    al = data.get("alignment") or data.get("normalized_alignment") or {}
    words, cur, start = [], "", None
    for ch, s, e in zip(al.get("characters", []), al.get("character_start_times_seconds", []),
                        al.get("character_end_times_seconds", [])):
        if ch.isspace():
            if cur:
                words.append({"text": cur, "start": start, "end": prev_end})
            cur, start = "", None
            continue
        if start is None:
            start = s
        cur += ch
        prev_end = e
    if cur:
        words.append({"text": cur, "start": start, "end": prev_end})
    (OUT / f"{name}.json").write_text(json.dumps({"text": text, "voice": voice, "model": MODEL, "words": words},
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    dur = words[-1]["end"] if words else 0
    print(f"  {mp3.relative_to(ROOT)} — {dur:.1f} с, {len(text)} симв.")
    return mp3


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--credits", action="store_true")
    ap.add_argument("--voices", action="store_true")
    ap.add_argument("--samples", nargs="+", metavar="VOICE_ID")
    ap.add_argument("--text", default=SAMPLE_TEXT, help="фраза для --samples")
    ap.add_argument("--voice")
    ap.add_argument("--blocks", help="id через запятую или all")
    ap.add_argument("--max-chars", type=int, default=1500)
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()

    if a.count:
        bl = blocks()
        for bid, t in bl.items():
            print(f"{bid:10} {len(t):5} симв.  ≈{len(t) / 15:4.0f} с")
        total = sum(len(t) for t in bl.values())
        print(f"{'всего':10} {total:5} симв.  ≈{total / 15 / 60:.1f} мин   ({MODEL}: ≈{total} кредитов)")
    elif a.credits:
        left, sub = remaining()
        print(f"Тариф {sub.get('tier')}: потрачено {sub.get('character_count')} из {sub.get('character_limit')}, "
              f"осталось {left}. Обновление: {sub.get('next_character_count_reset_unix')}")
    elif a.voices:
        for v in call("GET", "/v1/voices").get("voices", []):
            labels = v.get("labels") or {}
            print(f"{v['voice_id']}  {v['name'][:28]:28} {v.get('category', ''):10} "
                  f"{labels.get('language', '') or ''} {labels.get('gender', '') or ''} {labels.get('accent', '') or ''}")
    elif a.samples:
        guard(len(a.text) * len(a.samples), a.max_chars, a.yes)
        for vid in a.samples:
            tts(vid, a.text, f"sample-{vid}")
    elif a.voice and a.blocks:
        bl = blocks()
        ids = list(bl) if a.blocks == "all" else a.blocks.split(",")
        missing = [i for i in ids if i not in bl]
        if missing:
            sys.exit(f"Нет таких блоков: {missing}. Есть: {list(bl)}")
        guard(sum(len(bl[i]) for i in ids), a.max_chars, a.yes)
        for i in ids:
            tts(a.voice, bl[i], i)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
