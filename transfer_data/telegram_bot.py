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


async def format_table(content: dict) -> str:
    """
    Форматирует таблицу для отображения данных игры.

    Args:
        content (dict): Словарь с данными игры.

    Returns:
        str: Отформатированная таблица в виде строки.
    """
    opponent_0 = content['opponent_0'].center(25)
    opponent_1 = content['opponent_1'].center(25)
    site_liga = f"{content['site']} - {content['liga']}".center(58)

    total_label = "Total:".ljust(10)
    total_point = str(content['total_point']).center(8)
    total_bet_0 = str(content['total_bet_0']).ljust(8)
    total_bet_1 = str(content['total_bet_1']).ljust(8)

    handicap_label = "Handicap:".ljust(10)
    handicap_point_0 = str(content['handicap_point_0']).rjust(8)
    handicap_point_1 = str(content['handicap_point_1']).rjust(8)
    handicap_bet_0 = str(content['handicap_bet_0']).rjust(8)
    handicap_bet_1 = str(content['handicap_bet_1']).rjust(8)

    server_time = f"Server Time: {content['server_time']}"

    table = (
        f"|{'-' * 68}|\n"
        f"|{opponent_0} vs {opponent_1}|\n"
        f"|{site_liga}|\n"
        f"|{'-' * 68}|\n"
        f"|{total_label} | {total_point} | {total_bet_0} | {total_bet_1} {get_emoji_for_bet(total_bet_1)}|\n"
        f"|{'-' * 68}|\n"
        f"|{handicap_label} | {handicap_point_0} | {handicap_bet_0} | {handicap_point_1} | {handicap_bet_1}|\n"
        f"|{'-' * 68}|\n"
        f"|{server_time.center(66)}|\n"
        f"|{'-' * 68}|\n"
    )

    return table

def get_emoji_for_bet(bet: float) -> str:
    """
    Возвращает соответствующий эмодзи для коэффициента.

    :param bet: Коэффициент ставки
    :return: Строка с эмодзи
    """
    bet = float(bet)
    if bet <= 1.59:
        return "🟣"
    elif 1.60 <= bet <= 1.63:
        return "🔴"
    elif 1.64 <= bet <= 1.68:
        return "🟠"
    elif 1.69 <= bet <= 1.73:
        return "🟡"
    else:
        return ""


async def send_message_to_telegram(content: dict) -> None:
    """
    Отправляет данные в виде таблицы в Telegram чат.

    :param content: Словарь с данными, которые будут отправлены в виде таблицы
    """
    content['total_bet_0'] = float(content['total_bet_0'])
    content['total_bet_1'] = float(content['total_bet_1'])
    content['handicap_bet_0'] = float(content['handicap_bet_0'])
    content['handicap_bet_1'] = float(content['handicap_bet_1'])
    table = await format_table(content)
    try:
        print(table)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"```\n{table}\n```", parse_mode="Markdown")
    except TelegramError as e:
        print(f"Ошибка при отправке сообщения: {e}")
