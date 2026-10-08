"""Voice casting: the same phrase in several voices, sent to the Telegram review chat to pick by ear.

    docker compose exec video-mcp python -m video_mcp.reels.voice_samples
    docker compose exec video-mcp python -m video_mcp.reels.voice_samples --speed 1.1 "Свой текст"

The pick goes to .env: REELS_TTS=openai, REELS_OPENAI_TTS_MODEL=<model>, REELS_OPENAI_TTS_VOICE=<voice>
(for 'elevenlabs:<id>' — REELS_TTS=elevenlabs, REELS_ELEVENLABS_VOICE_ID=<id>), REELS_VOICE_SPEED=<speed>.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from . import tts
from .config import reels_settings
from .publish import _tg

TEXT = ("Купил VPN — а через месяц он умер. Вместе с деньгами. "
        "У многих дешёвых VPN один сервер на всех. Его заблокировали — и интернет пропал у всех разом.")

VOICES = [
    *(f"openai/gpt-4o-mini-tts:{v}" for v in ("onyx", "cedar", "marin", "ash", "ballad", "verse")),
    *(f"gemini/gemini-2.5-flash-preview-tts:{v}" for v in ("Charon", "Puck", "Fenrir", "Orus", "Iapetus")),
    *(f"gemini/gemini-2.5-pro-preview-tts:{v}" for v in ("Charon", "Puck")),
]


def candidates() -> list[str]:
    voices = list(VOICES)
    if reels_settings.elevenlabs_key and reels_settings.elevenlabs_voice:
        voices.append(f"elevenlabs:{reels_settings.elevenlabs_voice}")
    return voices


def run(text: str, voices: list[str], speed: float, send: bool = True) -> list[tuple[str, str]]:
    """Synthesize every voice; returns (spec, 'ok' or the error) per voice."""
    reels_settings.voice_speed = speed
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, spec in enumerate(voices, 1):
            out = Path(tmp) / f"{i:02d}.mp3"
            try:
                tts.synthesize(text, out, voice=spec)
                if send:
                    with out.open("rb") as f:
                        _tg("sendAudio", data={"chat_id": reels_settings.tg_review_chat,
                                               "caption": f"{i}. {spec} · темп {speed:g}",
                                               "title": f"{i}. {spec.rsplit(':', 1)[-1]}"},
                            files={"audio": (f"{i:02d}.mp3", f, "audio/mpeg")})
                results.append((spec, "ok"))
            except Exception as exc:  # one broken voice must not stop the casting
                results.append((spec, str(exc)[:200]))
            print(f"{i:2d}. {spec}: {results[-1][1]}", flush=True)
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", nargs="?", default=TEXT)
    ap.add_argument("--speed", type=float, default=1.1, help="tempo, 1.0 = as generated")
    ap.add_argument("--voice", action="append", help="only these voice specs (repeatable)")
    args = ap.parse_args()
    if not reels_settings.review_enabled:
        raise SystemExit("Set REELS_TG_BOT_TOKEN and REELS_TG_REVIEW_CHAT_ID: samples go to the review chat")
    results = run(args.text, args.voice or candidates(), args.speed)
    ok = sum(r == "ok" for _, r in results)
    _tg("sendMessage", json={"chat_id": reels_settings.tg_review_chat,
                             "text": f"Образцы голоса: {ok} из {len(results)}. Напиши Claude номер, который нравится."})


if __name__ == "__main__":
    main()
