import logging
import os
import threading

import requests
from flask import Flask, jsonify, request

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
PORT = int(os.getenv("PORT", "1000"))

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""
webhook_lock = threading.Lock()
webhook_configured = False


def telegram(method, payload=None):
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN Render Environment Variables ichida sozlanmagan.")
    response = requests.post(
        f"{TELEGRAM_API}/{method}",
        json=payload or {},
        timeout=(10, 25),
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API xatosi: {result}")
    return result


def ensure_webhook():
    global webhook_configured
    if webhook_configured:
        return
    with webhook_lock:
        if webhook_configured:
            return
        if not BOT_TOKEN:
            logging.error("TELEGRAM_BOT_TOKEN sozlanmagan.")
            return
        if not WEBHOOK_SECRET:
            logging.error("WEBHOOK_SECRET sozlanmagan.")
            return
        if not RENDER_URL:
            logging.error("RENDER_EXTERNAL_URL sozlanmagan.")
            return
        try:
            telegram("setWebhook", {
                "url": f"{RENDER_URL}/telegram/webhook",
                "secret_token": WEBHOOK_SECRET,
                "allowed_updates": ["message"],
            })
            webhook_configured = True
            logging.info("Telegram webhook sozlandi.")
        except Exception:
            logging.exception("Webhook sozlanmadi; keyingi so'rovda qayta uriniladi.")


def send_message(chat_id, text, keyboard=None):
    payload = {"chat_id": chat_id, "text": text}
    if keyboard:
        payload["reply_markup"] = keyboard
    return telegram("sendMessage", payload)


def handle_update(update):
    message = update.get("message")
    if not message:
        return

    chat_id = message.get("chat", {}).get("id")
    text = (message.get("text") or "").strip()
    if not chat_id:
        return

    if text == "/start":
        keyboard = {
            "keyboard": [
                [{"text": "🎬 Kinolar"}, {"text": "🔎 Kod orqali qidirish"}],
                [{"text": "⭐ Premium"}, {"text": "👤 Profil"}],
            ],
            "resize_keyboard": True,
        }
        send_message(
            chat_id,
            "🎬 TILAKINO Cinema'ga xush kelibsiz!\n\n"
            "Kino katalogi hozir admin tomonidan ruxsatli kino fayllari "
            "va ma'lumotlari qo'shilishini kutmoqda.",
            keyboard,
        )
    elif text == "🎬 Kinolar":
        send_message(chat_id, "🎞 Kino katalogi: hozircha katalogga kino qo'shilmagan.")
    elif text == "🔎 Kod orqali qidirish":
        send_message(chat_id, "🔢 Kino kodini yuboring. Masalan: 1024")
    elif text == "⭐ Premium":
        send_message(
            chat_id,
            "⭐ TILAKINO Premium narxlari:\n"
            "1 oy — 10 000 so'm\n"
            "2 oy — 20 000 so'm\n"
            "6 oy — 40 000 so'm\n"
            "1 yil — 60 000 so'm\n\n"
            "To'lovlar tizimi ulanmaguncha pul yubormang.",
        )
    elif text == "👤 Profil":
        send_message(chat_id, f"👤 Telegram ID: {chat_id}\nObuna: bepul tarif")
    elif text.isdigit():
        send_message(
            chat_id,
            f"🔎 {text} kodi bo'yicha kino topilmadi. "
            "Kino admin tomonidan katalogga qo'shilishi kerak.",
        )
    else:
        send_message(chat_id, "Buyruqni tushunmadim. Menyudan tanlang yoki /start bosing.")


@app.before_request
def configure_webhook_on_first_request():
    ensure_webhook()


@app.get("/")
def home():
    return jsonify({
        "service": "TILAKINO Telegram Bot",
        "status": "online",
        "port": PORT,
    }), 200


@app.get("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.post("/telegram/webhook")
def telegram_webhook():
    if not WEBHOOK_SECRET:
        return jsonify({"error": "server secret sozlanmagan"}), 503

    supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if supplied_secret != WEBHOOK_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    update = request.get_json(silent=True) or {}
    try:
        handle_update(update)
    except Exception:
        # Telegram'ga 200 qaytaramiz, shunda bitta xato update cheksiz qayta yuborilmaydi.
        logging.exception("Telegram update ishlashida xato")
    return jsonify({"ok": True}), 200


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN sozlanmagan.")
    if not WEBHOOK_SECRET:
        raise RuntimeError("WEBHOOK_SECRET sozlanmagan.")
    if not RENDER_URL:
        raise RuntimeError("RENDER_EXTERNAL_URL sozlanmagan.")
    ensure_webhook()
    app.run(host="0.0.0.0", port=PORT)
