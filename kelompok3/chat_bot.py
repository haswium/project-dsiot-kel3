"""
=============================================================
  Telegram Bot - Driver Heart Rate Monitor
  Sensor: MAX30102 | Device: Raspberry Pi | Broker: MQTT
=============================================================
Fitur:
  - /start          → Mulai monitoring & daftarkan chat_id
  - /stop           → Hentikan monitoring
  - /status         → Lihat BPM & SpO2 real-time
  - /history [n]    → Riwayat n data terakhir (default 10)
  - /setthreshold   → Atur batas BPM alert
  - /threshold      → Lihat threshold saat ini
  - Auto-alert      → Notifikasi otomatis saat BPM abnormal

Requirements:
  pip install python-telegram-bot paho-mqtt

Konfigurasi: isi bagian CONFIG di bawah
=============================================================
"""

import logging
import json
import threading
from datetime import datetime
from collections import deque

import paho.mqtt.client as mqtt
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ─────────────────────────────────────────
#  CONFIG — sesuaikan dengan setup kamu
# ─────────────────────────────────────────
TELEGRAM_TOKEN   = "7739066634:AAGeo3LLUIhMg7IKBev0pU0EEcGvShELX6g"   # dari @BotFather

MQTT_BROKER      = "100.88.25.26"             # IP broker MQTT (Mosquitto)
MQTT_PORT        = 1883
MQTT_TOPIC       = "/hrv"      # topic yang dikirim Raspberry Pi
MQTT_USERNAME    = ""                      # kosongkan jika tidak pakai auth
MQTT_PASSWORD    = ""

# Threshold default (bisa diubah via /setthreshold)
DEFAULT_BPM_MIN  = 55
DEFAULT_BPM_MAX  = 110

# Jumlah data histori yang disimpan di memori
HISTORY_SIZE     = 100
# ─────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── State global (in-memory, cukup untuk 1 driver / demo) ──
state = {
    "latest": None,          # dict: {bpm, spo2, timestamp}
    "history": deque(maxlen=HISTORY_SIZE),
    "subscribers": set(),    # chat_id yang aktif monitoring
    "threshold_min": DEFAULT_BPM_MIN,
    "threshold_max": DEFAULT_BPM_MAX,
    "alert_cooldown": {},    # chat_id → timestamp last alert (hindari spam)
}

# Referensi ke Application Telegram (diisi saat bot start)
_app: Application = None


# ════════════════════════════════════════════
#  MQTT — terima data dari Raspberry Pi
# ════════════════════════════════════════════

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"✅ Terhubung ke MQTT broker. Subscribe ke '{MQTT_TOPIC}'")
        client.subscribe(MQTT_TOPIC)
    else:
        logger.error(f"❌ Gagal connect MQTT, kode: {rc}")


def on_message(client, userdata, msg):
    """
    Terima payload JSON dari Raspberry Pi:
    {"bpm": 72, "spo2": 98, "timestamp": "2026-05-30T10:00:00"}
    """
    try:
        payload = json.loads(msg.payload.decode())
        bpm     = float(payload.get("bpm", 0))
        spo2    = float(payload.get("spo2", 0))
        ts      = payload.get("timestamp", datetime.now().isoformat())

        data = {"bpm": bpm, "spo2": spo2, "timestamp": ts}
        state["latest"]  = data
        state["history"].append(data)

        logger.info(f"📡 Data diterima → BPM: {bpm}, SpO2: {spo2}%")

        # Cek apakah perlu kirim alert
        _check_and_alert(bpm, spo2, ts)

    except Exception as e:
        logger.error(f"Error parsing MQTT message: {e}")


def _check_and_alert(bpm: float, spo2: float, ts: str):
    """Kirim notifikasi Telegram jika BPM di luar threshold."""
    if _app is None or not state["subscribers"]:
        return

    tmin = state["threshold_min"]
    tmax = state["threshold_max"]

    if bpm < tmin:
        status  = "😴 NGANTUK / KELELAHAN"
        warning = f"BPM terlalu rendah ({bpm:.0f} < {tmin})"
    elif bpm > tmax:
        status  = "⚡ STRES / KELELAHAN TINGGI"
        warning = f"BPM terlalu tinggi ({bpm:.0f} > {tmax})"
    elif spo2 < 95:
        status  = "⚠️ SpO2 RENDAH"
        warning = f"Saturasi oksigen rendah ({spo2:.0f}%)"
    else:
        return  # Normal, tidak perlu alert

    now = datetime.now().timestamp()
    message = (
        f"🚨 *PERINGATAN DRIVER!*\n\n"
        f"Status  : {status}\n"
        f"BPM     : *{bpm:.0f}* bpm\n"
        f"SpO2    : *{spo2:.0f}%*\n"
        f"Waktu   : {_fmt_time(ts)}\n\n"
        f"⚠️ _{warning}_\n\n"
        f"Segera istirahat dan pinggirkan kendaraan!"
    )

    for chat_id in list(state["subscribers"]):
        # Cooldown 60 detik per chat agar tidak spam
        last = state["alert_cooldown"].get(chat_id, 0)
        if now - last < 60:
            continue
        state["alert_cooldown"][chat_id] = now
        threading.Thread(
            target=_send_message_sync,
            args=(chat_id, message),
            daemon=True
        ).start()


def _send_message_sync(chat_id: int, text: str):
    """Kirim pesan Telegram dari thread non-async (MQTT thread)."""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            _app.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown"
            )
        )
        loop.close()
    except Exception as e:
        logger.error(f"Gagal kirim alert ke {chat_id}: {e}")


def start_mqtt():
    client = mqtt.Client()
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_forever()


# ════════════════════════════════════════════
#  TELEGRAM COMMAND HANDLERS
# ════════════════════════════════════════════

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [["/status", "/history"], ["/threshold", "/setthreshold"], ["/stop"]],
    resize_keyboard=True
)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state["subscribers"].add(chat_id)
    await update.message.reply_text(
        "✅ *Monitoring driver aktif!*\n\n"
        "Kamu akan menerima notifikasi otomatis jika detak jantung driver "
        "melewati batas aman.\n\n"
        "Gunakan menu di bawah untuk navigasi:",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD
    )


async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state["subscribers"].discard(chat_id)
    await update.message.reply_text(
        "🔕 Monitoring dihentikan. Ketik /start untuk mengaktifkan kembali."
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = state["latest"]
    if data is None:
        await update.message.reply_text(
            "📡 Belum ada data dari sensor. Pastikan Raspberry Pi sudah mengirim data."
        )
        return

    bpm  = data["bpm"]
    spo2 = data["spo2"]
    ts   = data["timestamp"]
    tmin = state["threshold_min"]
    tmax = state["threshold_max"]

    # Tentukan status
    if bpm < tmin:
        kondisi = "😴 Ngantuk / Kelelahan"
        bar     = "🔴🔴🔴🔴🔴"
    elif bpm > tmax:
        kondisi = "⚡ Stres / Kelelahan Tinggi"
        bar     = "🔴🔴🔴🔴🔴"
    else:
        kondisi = "✅ Normal"
        bar     = "🟢🟢🟢🟢🟢"

    spo2_status = "✅ Normal" if spo2 >= 95 else "⚠️ Rendah"

    await update.message.reply_text(
        f"📊 *Status Real-Time Driver*\n"
        f"{'─' * 25}\n"
        f"❤️ BPM    : *{bpm:.0f} bpm*  {bar}\n"
        f"💨 SpO2   : *{spo2:.0f}%*  {spo2_status}\n"
        f"🩺 Kondisi: {kondisi}\n"
        f"🕐 Update : {_fmt_time(ts)}\n"
        f"{'─' * 25}\n"
        f"Threshold: {tmin}–{tmax} bpm",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD
    )


async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    n = 10
    if ctx.args:
        try:
            n = max(1, min(int(ctx.args[0]), 50))
        except ValueError:
            pass

    history = list(state["history"])[-n:]
    if not history:
        await update.message.reply_text("📂 Belum ada riwayat data.")
        return

    lines = [f"📋 *Riwayat {n} Data Terakhir*\n{'─'*25}"]
    for i, d in enumerate(reversed(history), 1):
        bpm  = d["bpm"]
        spo2 = d["spo2"]
        icon = "✅" if state["threshold_min"] <= bpm <= state["threshold_max"] else "⚠️"
        lines.append(
            f"{i:2}. {icon} BPM: *{bpm:.0f}* | SpO2: {spo2:.0f}% | {_fmt_time(d['timestamp'])}"
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD
    )


async def cmd_setthreshold(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Penggunaan: /setthreshold 55 110
    """
    if len(ctx.args) != 2:
        await update.message.reply_text(
            "⚙️ *Cara pakai:*\n`/setthreshold [min] [max]`\n\n"
            "Contoh: `/setthreshold 55 110`",
            parse_mode="Markdown"
        )
        return

    try:
        bmin = int(ctx.args[0])
        bmax = int(ctx.args[1])
        if bmin >= bmax or bmin < 30 or bmax > 200:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ Nilai tidak valid. Min harus < Max, rentang 30–200."
        )
        return

    state["threshold_min"] = bmin
    state["threshold_max"] = bmax
    await update.message.reply_text(
        f"✅ Threshold berhasil diubah!\n\n"
        f"BPM Min : *{bmin}*\n"
        f"BPM Max : *{bmax}*\n\n"
        f"Alert akan dikirim jika BPM di luar rentang ini.",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD
    )


async def cmd_threshold(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tmin = state["threshold_min"]
    tmax = state["threshold_max"]
    await update.message.reply_text(
        f"⚙️ *Threshold Saat Ini*\n\n"
        f"BPM Min : *{tmin}* (di bawah ini = ngantuk/lelah)\n"
        f"BPM Max : *{tmax}* (di atas ini = stres/kelelahan)\n\n"
        f"Ubah dengan: `/setthreshold [min] [max]`",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD
    )


# ════════════════════════════════════════════
#  HELPER
# ════════════════════════════════════════════

def _fmt_time(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return ts


# ════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════

def main():
    global _app

    # Jalankan MQTT di background thread
    mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
    mqtt_thread.start()
    logger.info("🚀 MQTT thread started")

    # Setup Telegram bot
    _app = Application.builder().token(TELEGRAM_TOKEN).build()
    _app.add_handler(CommandHandler("start",         cmd_start))
    _app.add_handler(CommandHandler("stop",          cmd_stop))
    _app.add_handler(CommandHandler("status",        cmd_status))
    _app.add_handler(CommandHandler("history",       cmd_history))
    _app.add_handler(CommandHandler("setthreshold",  cmd_setthreshold))
    _app.add_handler(CommandHandler("threshold",     cmd_threshold))

    logger.info("🤖 Bot Telegram berjalan... (Ctrl+C untuk berhenti)")
    _app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
