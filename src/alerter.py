from telegram import Bot
from telegram.constants import ParseMode


def escape_md(text):
    chars = "_*[]()~`>#+-=|{}.!"
    for c in chars:
        text = text.replace(c, f"\\{c}")
    return text


class TelegramAlerter:
    def __init__(self, token, chat_id):
        self.bot = Bot(token=token)
        self.chat_id = chat_id

    async def send_signal(self, signal):
        emoji = "🔴" if signal.get("premium_zscore", 0) > 3 else "🟡"
        direction = "CALL" if signal["option_type"] == "C" else "PUT"

        msg = (
            f"{emoji} *Unusual Options Activity* — {signal['ticker']} {direction}\n\n"
            f"• Strike: \\${signal['strike']} | Exp: {signal['expiration']}\n"
            f"• Price: \\${signal['price']} | Vol: {signal['volume']:,} | OI: {signal['open_interest']:,}\n"
            f"• Vol/OI Ratio: {signal.get('vol_oi_ratio', 'N/A')}\n"
            f"• Premium: \\${signal['premium_usd']:,.0f}\n"
            f"• Delta: {signal.get('delta', 'N/A')} | IV: {signal.get('iv', 0) * 100:.1f}%\n"
            f"• Reason: {escape_md(signal.get('reason', 'unknown'))}"
        )

        await self.bot.send_message(
            chat_id=self.chat_id,
            text=msg,
            parse_mode=ParseMode.MARKDOWN_V2
        )

    async def send_error(self, error_msg):
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=f"⚠️ *bot\\-options Error*\n{escape_md(str(error_msg))}",
            parse_mode=ParseMode.MARKDOWN_V2
        )
