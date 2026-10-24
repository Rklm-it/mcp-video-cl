#!/usr/bin/env python3
"""Демо-Brain для съёмки промо панели Nexus.

Отдаёт панели правдоподобные, но ВЫДУМАННЫЕ данные: ноды, клиенты, платежи,
выручка. Настоящих клиентов, доменов, IP и сумм в кадре быть не должно
(решение владельца, docs/nexus/README.md), поэтому всё здесь сгенерировано
с фиксированным зерном — кадры воспроизводятся от прогона к прогону.

За основу взята заглушка смоук-теста панели (vgx3d/frontend/tests/e2e/
mock-brain.py): та же форма ответов, только данных больше и они «живые».
Неизвестная ручка отдаёт пустой список — страница не падает.

Запуск: python3 demo-brain.py [порт]
"""
from __future__ import annotations

import json
import random
import sys
import uuid
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
NOW = datetime(2026, 10, 24, 18, 30)
rnd = random.Random(2026)

# ── Ноды ──
NODE_SEED = [
    ("nl-amsterdam-1", "NL", "Amsterdam", 48, 31),
    ("de-frankfurt-1", "DE", "Frankfurt", 61, 44),
    ("fi-helsinki-1", "FI", "Helsinki", 37, 22),
    ("se-stockholm-1", "SE", "Stockholm", 29, 17),
    ("pl-warsaw-1", "PL", "Warsaw", 33, 19),
    ("ru-moscow-cdn", "RU", "Moscow", 72, 58),
    ("tr-istanbul-1", "TR", "Istanbul", 24, 12),
    ("kz-almaty-1", "KZ", "Almaty", 18, 9),
    ("us-newyork-1", "US", "New York", 15, 7),
]
NODES = [
    {
        "id": str(uuid.UUID(int=i + 1)),
        "name": name,
        "ip_address": f"10.20.0.{i + 11}",
        "api_port": 9090,
        "country": country,
        "city": city,
        "display_name": city,
        "sub_type": "bypass" if country == "RU" else "vpn",
        "protocols": ["reality", "xhttp", "hysteria2"],
        "is_active": True,
        "is_online": True,
        "is_free": False,
        "free_for_all": False,
        "router_enabled": False,
        "reputation_status": "clean",
        "reputation_score": 92,
        "rf_status": "ok",
        "display_order": (i + 1) * 10,
        "created_at": f"2026-0{1 + i % 9}-05T00:00:00",
        "total_traffic": users * 9 * 10**9,
        "vpn_traffic": users * 9 * 10**9,
        "bypass_traffic": 0,
        "active_users": users * 6,
        "online_users": online,
        "agent_version": "3.105.11",
        "last_heartbeat_at": (NOW - timedelta(seconds=8 + i)).isoformat(),
    }
    for i, (name, country, city, users, online) in enumerate(NODE_SEED)
]

# ── Клиенты ──
NICKS = [
    "alexey_m", "marina.k", "dmitry_v", "olga_s", "ivan_petrov", "kate_lis",
    "sergey_n", "anna_b", "maxim.t", "yulia_r", "pavel_g", "nastya_v",
    "artem_k", "elena_d", "roman_f", "vika_m", "nikita_s", "daria_p",
    "igor_z", "polina_a", "denis_o", "sofia_e", "kirill_l", "alina_c",
]
PLANS = [("Месяц", 299.0, 30, 100), ("3 месяца", 790.0, 90, 300), ("Год", 2490.0, 365, 0)]


def make_user(i: int, nick: str) -> dict:
    plan = PLANS[i % 3]
    used = rnd.randint(2, 90) * 1024**3
    expire = NOW + timedelta(days=rnd.randint(3, 200))
    return {
        "id": str(uuid.UUID(int=0x1000 + i)),
        "username": nick,
        "email": None,
        "vless_uuid": str(uuid.UUID(int=0x2000 + i)),
        "sub_token": f"demo{i:04d}",
        "telegram_id": 5_100_000_000 + i * 7919,
        "traffic_limit": plan[3] * 1024**3,
        "traffic_used": min(used, plan[3] * 1024**3) if plan[3] else used,
        "speed_limit": 0,
        "ip_limit": 3,
        "device_limit": 3,
        "is_active": True,
        "bypass_active": i % 4 == 0,
        "bypass_traffic_used": 0,
        "bypass_traffic_limit": 0,
        "is_blocked": False,
        "balance": float(rnd.choice([0, 0, 50, 120, 300])),
        "auto_renew": i % 3 == 0,
        "expire_at": expire.isoformat(),
        "created_at": (NOW - timedelta(days=rnd.randint(5, 300))).isoformat(),
        "plan_title": plan[0],
        "is_online": i % 2 == 0,
        "online_ips": 1 if i % 2 == 0 else 0,
        "servers": [n["id"] for n in NODES[: 3 + i % 5]],
    }


USERS = [make_user(i, n) for i, n in enumerate(NICKS)]
TOTAL_USERS = 1284

# ── Платежи ──
PAYMENTS = []
for i in range(30):
    u = USERS[(i * 5) % len(USERS)]
    plan = PLANS[(i * 7) % 3]
    at = NOW - timedelta(minutes=17 + i * 53)
    PAYMENTS.append({
        "id": str(uuid.UUID(int=0xA000 + i)),
        "order_id": f"NX-{240000 + i * 37}",
        "platega_tx_id": None,
        "user_id": u["id"],
        "username": u["username"],
        "telegram_id": u["telegram_id"],
        "plan_id": None,
        "plan_title": plan[0],
        "amount": plan[1],
        "currency": "RUB",
        "status": "pending" if i % 9 == 4 else "success",
        "provider": "platega",
        "traffic_bytes": plan[3] * 1024**3,
        "days": plan[2],
        "created_at": at.isoformat(),
        "paid_at": (at + timedelta(minutes=1)).isoformat(),
    })

REVENUE_BY_DAY = []
for d in range(30, -1, -1):
    day = NOW - timedelta(days=d)
    base = 9_000 + (30 - d) * 260
    REVENUE_BY_DAY.append({
        "date": day.date().isoformat(),
        "revenue": float(base + rnd.randint(-1800, 2400)),
        "count": 25 + (30 - d) + rnd.randint(-5, 9),
    })


def dashboard() -> dict:
    return {
        "finance": {
            "revenue_24h": REVENUE_BY_DAY[-1]["revenue"],
            "revenue_7d": sum(r["revenue"] for r in REVENUE_BY_DAY[-7:]),
            "revenue_30d": sum(r["revenue"] for r in REVENUE_BY_DAY[-30:]),
        },
        "users": {"total": TOTAL_USERS, "active": 1093, "online": 412, "new_today": 37, "blocked": 6},
        "servers": {"total": len(NODES), "online": len(NODES)},
        "system": {
            "cpu_percent": 23.0, "ram_percent": 41.0, "ram_used_gb": 1.6, "ram_total_gb": 4.0,
            "disk_percent": 34.0, "disk_used_gb": 27.0, "disk_total_gb": 80.0,
        },
    }


def analytics() -> dict:
    return {
        "revenue_by_day": REVENUE_BY_DAY,
        "finance_summary": {
            "avg_check": 612.0, "conversion": 38.4, "paying_users": 493, "total_users": TOTAL_USERS,
        },
        "server_traffic": [
            {"id": n["id"], "name": n["name"], "is_online": True, "total_traffic": n["total_traffic"]}
            for n in NODES
        ],
        "dealer_analytics": {
            "summary": {
                "dealers_active": 4, "dealers_total": 5, "keys_total": 318, "keys_paid": 287,
                "keys_pending": 19, "keys_expired": 12, "payment_rate": 90.2, "total_topups": 84500.0,
            },
            "top_dealers": [],
            "revenue_by_day": [],
        },
    }


def payment_stats() -> dict:
    ok = [p for p in PAYMENTS if p["status"] == "success"]
    day = {"sum": REVENUE_BY_DAY[-1]["revenue"], "count": REVENUE_BY_DAY[-1]["count"]}
    week = {"sum": sum(r["revenue"] for r in REVENUE_BY_DAY[-7:]), "count": sum(r["count"] for r in REVENUE_BY_DAY[-7:])}
    month = {"sum": sum(r["revenue"] for r in REVENUE_BY_DAY[-30:]), "count": sum(r["count"] for r in REVENUE_BY_DAY[-30:])}
    return {"day": day, "week": week, "month": month, "all": {"sum": month["sum"] * 6.2, "count": month["count"] * 6},
            "last_paid_at": ok[0]["paid_at"], "total_payments": month["count"] * 6}


def users_list(query: str) -> dict:
    q = ""
    for part in query.split("&"):
        if part.startswith("search="):
            q = part.split("=", 1)[1].lower()
    items = [u for u in USERS if q in u["username"].lower()] if q else USERS
    return {"total": len(items) if q else TOTAL_USERS, "items": items}


def sub_order() -> dict:
    return {"mode": "manual", "group": "protocol", "offline_last": True, "client_choice": False,
            "protocols": [], "protocols_custom": False, "servers": NODES}


def sub_order_preview() -> dict:
    return {
        "mode": "manual", "group": "protocol", "sub_type": "vpn",
        "nodes": [{"id": n["id"], "name": n["name"], "display_name": n["city"], "is_online": True,
                   "display_order": n["display_order"]} for n in NODES],
        "lines": [f"{n['city']} · Reality" for n in NODES],
        "manual_ignored": False,
    }


ROUTES = {
    "/api/v1/admin/sub-order": lambda q: sub_order(),
    "/api/v1/admin/sub-order/preview": lambda q: sub_order_preview(),
    "/api/v1/admin/resync": lambda q: {"enabled": True, "interval_h": 6, "remove_extra": True, "last_run": None},
    "/api/v1/admin/resync/progress": lambda q: {"state": "idle"},
    "/api/v1/admin/nodes/upgrade-all/status": lambda q: {"state": "idle"},
    "/api/v1/admin/nodes/geosite/categories": lambda q: {"categories": ["category-ru", "youtube"]},

    "/api/v1/servers": lambda q: NODES,
    "/api/v1/servers/live-stats": lambda q: {"stats": {n["id"]: {"ok": True, "ping_ms": 18 + i * 4} for i, n in enumerate(NODES)}},
    "/api/v1/admin/dashboard": lambda q: dashboard(),
    "/api/v1/admin/analytics": lambda q: analytics(),
    "/api/v1/admin/payments": lambda q: PAYMENTS,
    "/api/v1/admin/payments/stats": lambda q: payment_stats(),
    "/api/v1/admin/users": users_list,
    "/api/v1/health": lambda q: {"status": "ok", "version": "3.105.11"},
    "/api/v1/admin/health": lambda q: {"status": "ok"},
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, payload, code: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        path, _, query = self.path.partition("?")
        route = ROUTES.get(path)
        if route is not None:
            return self._send(route(query))
        if path.startswith("/api/v1/users/"):
            uid = path.rsplit("/", 1)[-1]
            user = next((u for u in USERS if u["id"] == uid), None)
            return self._send(user or {"detail": "Пользователь не найден"}, code=200 if user else 404)
        return self._send([])

    def do_POST(self):  # noqa: N802
        self._send({"ok": True})

    do_PUT = do_PATCH = do_DELETE = do_POST


if __name__ == "__main__":
    print(f"demo brain on http://127.0.0.1:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
