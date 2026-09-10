import os
import asyncio
import yt_dlp

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ.get("BOT_TOKEN")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def download_video(url):
    options = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",

        # Сначала пробуем готовый MP4
        "format": "best[ext=mp4]/best",

        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,

        # Настройки для YouTube
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            }
        },

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13) "
                "AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36"
            )
        },
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

        base, ext = os.path.splitext(filename)

        if os.path.exists(base + ".mp4"):
            filename = base + ".mp4"

        return filename


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет!\n\n"
        "Отправь ссылку на видео с YouTube, TikTok или Instagram."
    )


async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not any(
        site in url.lower()
        for site in [
            "youtube.com",
            "youtu.be",
            "tiktok.com",
            "instagram.com",
        ]
    ):
        await update.message.reply_text(
            "❌ Отправь ссылку на YouTube, TikTok или Instagram."
        )
        return

    message = await update.message.reply_text(
        "⏳ Скачиваю видео..."
    )

    filename = None

    try:
        filename = await asyncio.to_thread(
            download_video,
            url
        )

        if not os.path.exists(filename):
            raise Exception("Файл не найден")

        size = os.path.getsize(filename)

        if size > 49 * 1024 * 1024:
            await message.edit_text(
                "❌ Видео слишком большое для отправки."
            )
            os.remove(filename)
            return

        await message.edit_text(
            "📤 Отправляю видео казанбаш..."
        )

        with open(filename, "rb") as video:
            await update.message.reply_video(
                video=video,
                caption="✅ Готово!"
            )

        await message.delete()

    except Exception as error:
        print("ERROR:", error)

        await message.edit_text(
            "❌ YouTube не разрешил скачать это видео.\n\n"
            "Попробуй другую ссылку."
        )

    finally:
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except:
                pass


def main():
    if not TOKEN:
        print("BOT_TOKEN не установлен!")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            download
        )
    )

    print("🤖 Бот запущен!")

    app.run_polling()


if __name__ == "__main__":
    main()
