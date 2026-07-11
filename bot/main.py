"""Telegram bot entrypoint (python-telegram-bot v21+).

Usage:
    python -m bot.main            # requires TELEGRAM_BOT_TOKEN (+ ANTHROPIC/TAVILY keys)

Commands:
    /start              - greeting + help
    /research <query>   - run the LangGraph research agent and reply with the
                          edited markdown answer + sources.

Phase 2 wiring: the Telegram ``chat_id`` is used as the episodic-memory
``session_id`` so the agent recalls this chat's last 3 searches. The heavy,
blocking graph run is executed in a worker thread so the bot stays responsive.
"""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from agent.graph import run_research
from settings import get_settings

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _summarize(markdown: str, limit: int = 280) -> str:
    text = markdown.strip().replace("\n", " ")
    return text[:limit]


async def _build_memory():
    """Best-effort episodic memory; returns None if Redis is unreachable."""
    try:
        from memory import EpisodicMemory

        mem = EpisodicMemory.from_url()
        await mem.redis.ping()
        return mem
    except Exception as exc:  # pragma: no cover - depends on a live Redis
        logger.warning("Episodic memory disabled (Redis unavailable): %s", exc)
        return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi! I'm your research assistant.\n\n"
        "Use /research <your question> and I'll look it up and write you an answer."
    )


async def research(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        await update.message.reply_text("Usage: /research <your question>")
        return

    chat_id = str(update.effective_chat.id)
    status = await update.message.reply_text("Researching... this may take a moment.")

    mem = context.application.bot_data.get("memory")
    recall = []
    if mem is not None:
        try:
            recall = await mem.recall(chat_id)
        except Exception as exc:
            logger.warning("recall failed: %s", exc)

    try:
        # The graph is synchronous/blocking -> run off the event loop.
        result = await asyncio.to_thread(
            run_research, query, session_id=chat_id, recall=recall
        )
    except Exception as exc:  # the graph is built to degrade, but be safe
        logger.exception("research failed")
        await status.edit_text(f"Sorry, research failed: {exc}")
        return

    markdown = result.get("markdown", "")
    if mem is not None:
        try:
            await mem.remember(chat_id, query, summary=_summarize(markdown))
        except Exception as exc:
            logger.warning("remember failed: %s", exc)

    # Telegram messages cap at 4096 chars.
    text = markdown[:4000] if markdown else "No answer produced."
    try:
        await status.edit_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await status.edit_text(text)  # fall back to plain text if markdown breaks


def build_application(token: str | None = None) -> Application:
    settings = get_settings()
    token = token or settings.telegram_bot_token
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Add it to your environment / .env file."
        )

    application = Application.builder().token(token).post_init(_post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("research", research))
    return application


async def _post_init(application: Application) -> None:
    application.bot_data["memory"] = await _build_memory()


def main() -> None:
    application = build_application()
    logger.info("Starting Telegram bot (polling)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
