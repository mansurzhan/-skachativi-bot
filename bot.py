import asyncio
import os
import shutil
import tempfile
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import yt_dlp

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден в .env")

bot = Bot(TOKEN)
dp = Dispatcher()

# Временное хранилище ссылок пользователей
user_urls = {}


def main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎥 Видео", callback_data="video"),
                InlineKeyboardButton(text="🎵 MP3", callback_data="mp3"),
            ]
        ]
    )


def quality_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="144p", callback_data="q_144"),
                InlineKeyboardButton(text="240p", callback_data="q_240"),
            ],
            [
                InlineKeyboardButton(text="360p", callback_data="q_360"),
                InlineKeyboardButton(text="480p", callback_data="q_480"),
            ],
            [
                InlineKeyboardButton(text="720p", callback_data="q_720"),
                InlineKeyboardButton(text="1080p", callback_data="q_1080"),
            ],
            [
                InlineKeyboardButton(text="🔥 Лучшее", callback_data="q_best"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
            ],
        ]
    )


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Привет!\n\n"
        "Отправь мне ссылку на видео с YouTube, TikTok или Instagram.",
        parse_mode="HTML"
    )


@dp.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "📖 <b>Как пользоваться:</b>\n\n"
        "1. Отправь ссылку на видео.\n"
        "2. Выбери 🎥 Видео или 🎵 MP3.\n"
        "3. Для видео выбери качество.\n"
        "4. Дождись окончания загрузки.",
        parse_mode="HTML"
    )


@dp.message(F.text)
async def get_url(message: Message):
    url = message.text.strip()

    if not (
        "youtube.com" in url
        or "youtu.be" in url
        or "tiktok.com" in url
        or "instagram.com" in url
    ):
        await message.answer(
            "❌ Пожалуйста, отправь ссылку на YouTube, TikTok или Instagram."
        )
        return

    user_urls[message.from_user.id] = url

    await message.answer(
        "Что скачать?",
        reply_markup=main_keyboard()
    )


@dp.callback_query(F.data == "video")
async def video_callback(callback: CallbackQuery):
    await callback.answer()

    await callback.message.edit_text(
        "🎥 Выбери качество:",
        reply_markup=quality_keyboard()
    )


@dp.callback_query(F.data == "mp3")
async def mp3_callback(callback: CallbackQuery):
    await callback.answer()

    user_id = callback.from_user.id
    url = user_urls.get(user_id)

    if not url:
        await callback.message.edit_text("❌ Ссылка устарела. Отправь её заново.")
        return

    await callback.message.edit_text("🔎 Получаю информацию...")

    await download_mp3(callback.message, url)


@dp.callback_query(F.data.startswith("q_"))
async def quality_callback(callback: CallbackQuery):
    await callback.answer()

    user_id = callback.from_user.id
    url = user_urls.get(user_id)

    if not url:
        await callback.message.edit_text("❌ Ссылка устарела. Отправь её заново.")
        return

    quality = callback.data.replace("q_", "")

    await callback.message.edit_text(
        f"⬇️ Начинаю скачивание...\n"
        f"Качество: {quality}"
    )

    await download_video(callback.message, url, quality)


@dp.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery):
    await callback.answer("Отменено")

    user_urls.pop(callback.from_user.id, None)

    await callback.message.edit_text(
        "❌ Загрузка отменена."
    )


async def download_video(message: Message, url: str, quality: str):
    temp_dir = Path(tempfile.mkdtemp())

    try:
        output = str(temp_dir / "%(title).100s.%(ext)s")

        if quality == "best":
            fmt = "bv*+ba/b"
        else:
            height = int(quality)
            fmt = (
                f"bv*[height<={height}]+ba/"
                f"b[height<={height}]/"
                f"b"
            )

        ydl_opts = {
            "format": fmt,
            "outtmpl": output,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }

        await message.edit_text("⬇️ Скачивание...")

        await asyncio.to_thread(
            run_yt_dlp,
            url,
            ydl_opts
        )

        files = list(temp_dir.iterdir())

        if not files:
            raise RuntimeError("Файл не был скачан.")

        file_path = files[0]

        await message.edit_text("📤 Отправляю файл...")

        from aiogram.types import FSInputFile

        await message.answer_video(
            video=FSInputFile(file_path),
            caption="✅ Готово!"
        )

    except Exception as e:
        print("DOWNLOAD ERROR:", e)

        await message.edit_text(
            "❌ Не удалось скачать видео.\n\n"
            "Возможно, видео недоступно или превышен размер файла."
        )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def download_mp3(message: Message, url: str):
    temp_dir = Path(tempfile.mkdtemp())

    try:
        output = str(temp_dir / "%(title).100s.%(ext)s")

        ydl_opts = {
            "format": "ba/b",
            "outtmpl": output,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

        await message.edit_text("🎵 Скачиваю аудио...")

        await asyncio.to_thread(
            run_yt_dlp,
            url,
            ydl_opts
        )

        files = list(temp_dir.glob("*.mp3"))

        if not files:
            raise RuntimeError("MP3 не создан.")

        file_path = files[0]

        await message.edit_text("📤 Отправляю MP3...")

        from aiogram.types import FSInputFile

        await message.answer_audio(
            audio=FSInputFile(file_path),
            caption="🎵 Готово!"
        )

    except Exception as e:
        print("MP3 ERROR:", e)

        await message.edit_text(
            "❌ Не удалось получить MP3."
        )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_yt_dlp(url, options):
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])


async def main():
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
