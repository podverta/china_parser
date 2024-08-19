import os
from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv


# Загрузка переменных окружения из .env файла
load_dotenv()

TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Инициализация бота
bot = Bot(token=TELEGRAM_BOT_TOKEN)


def get_emoji_for_bet(bet: float) -> str:
    """
    Возвращает соответствующий эмодзи для коэффициента.

    :param bet: Коэффициент ставки
    :return: Строка с эмодзи
    """
    if 0 < bet <= 1.59:
        return "🟣"
    elif 1.60 <= bet <= 1.63:
        return "🔴"
    elif 1.64 <= bet <= 1.68:
        return "🟠"
    elif 1.69 <= bet <= 1.73:
        return "🟡"
    else:
        return ""  # Если коэффициент вне указанных диапазонов, возвращаем пустую строку


async def send_message_to_telegram(content: dict) -> None:
    """
    Отправляет данные в виде таблицы в Telegram чат.

    :param content: Словарь с данными, которые будут отправлены в виде таблицы
    """

    total_bet_0 = float(content.get('total_bet_0', '0'))
    total_bet_1 = float(content.get('total_bet_1', '0'))
    handicap_bet_0 = float(content.get('handicap_bet_0', '0'))
    handicap_bet_1 = float(content.get('handicap_bet_1', '0'))

    table = (
        f"{content['opponent_0']} vs {content['opponent_1']} | {content['site']} - {content['liga']}\n"
        f"Total: {content['total_point']}|{total_bet_0} {get_emoji_for_bet(total_bet_0)}|{total_bet_1} {get_emoji_for_bet(total_bet_1)}\n"
        f"Handicap: {content['handicap_point_0']}|{handicap_bet_0} {get_emoji_for_bet(handicap_bet_0)}|{content['handicap_point_1']}|{handicap_bet_1} {get_emoji_for_bet(handicap_bet_1)}\n"
        f"Server Time: {content['server_time']}"
    )
    try:
        # Отправка сообщения в чат с использованием моноширинного шрифта для таблицы
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"```\n{table}\n```", parse_mode="Markdown")
    except TelegramError as e:
        print(f"Ошибка при отправке сообщения: {e}")
