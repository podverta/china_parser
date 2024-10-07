import os
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

# Загрузка переменных окружения из .env файла
load_dotenv()

TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

TG_CHAT_RBL = os.getenv('TG_CHAT_RBL')
TG_CHAT_RBLW = os.getenv('TG_CHAT_RBLW')
TG_CHAT_IPBL1 = os.getenv('TG_CHAT_IPBL1')
TG_CHAT_IPBL2 = os.getenv('TG_CHAT_IPBL2')
TG_CHAT_IPBLW = os.getenv('TG_CHAT_IPBLW')

LEAGUES = {
    'IPBL Pro Division': TG_CHAT_IPBL1,
    'IPBL Pro Division Women': TG_CHAT_IPBLW,
    'Rocket Basketball League': TG_CHAT_RBL,
    'Rocket Basketball League Women': TG_CHAT_RBLW,
}

IPBL1_TEAMS = [
    "kazan",
    "saint petersburg",
    "sochi",
    "moscow",
    "kuban",
    "kamchatka",
    "siberia",
    "ural",
    "vladivostok",
    "novosibirsk",
    "kaliningrad",
    "samara",
    "yenisei",
    "oka",
    "don",
    "volga",
    "surgut",
    "barnaul",
    "krasnodar",
    "omsk",
]

# Инициализация бота
bot = Bot(token=TELEGRAM_BOT_TOKEN)


def get_emoji_for_bet(bet: float) -> tuple[str, bool]:
    """
    Возвращает соответствующий эмодзи для коэффициента и флаг необходимости триггера.

    :param bet: Коэффициент ставки
    :return: Кортеж, содержащий эмодзи и флаг (True, если эмодзи триггерное)
    """
    if 0 < bet <= 1.59:
        return "🟣", True
    elif 1.60 <= 1.63:
        return "🔴", True
    elif 1.64 <= 1.68:
        return "🟠", True
    elif 1.69 <= 1.73:
        return "🟡", False
    else:
        return "", False  # Если коэффициент вне указанных диапазонов, возвращаем пустую строку


async def send_message_to_telegram(
        content: dict,
        content_2: dict = None
) -> None:
    """
    Отправляет данные в виде таблицы в Telegram чат.

    :param content: Словарь с данными, которые будут отправлены в виде таблицы
    :param content_2: Словарь с данными другого сайта, которые будут отправлены в виде таблицы
    """
    trigger_bk_0 = False
    trigger_bk_1 = False

    # Коэффициенты для первой букмекерской конторы (content)
    total_bet_0 = float(content.get('total_bet_0', '0'))
    total_bet_1 = float(content.get('total_bet_1', '0'))
    handicap_bet_0 = float(content.get('handicap_bet_0', '0'))
    handicap_bet_1 = float(content.get('handicap_bet_1', '0'))
    opponent_0 = content.get('opponent_0', '')
    opponent_1 = content.get('opponent_1', '')
    liga = content['liga']
    site = content['site']

    # Проверка коэффициентов для первой букмекерской конторы
    emoji_total_0, trigger_total_0 = get_emoji_for_bet(total_bet_0)
    emoji_total_1, trigger_total_1 = get_emoji_for_bet(total_bet_1)
    emoji_handicap_0, trigger_handicap_0 = get_emoji_for_bet(handicap_bet_0)
    emoji_handicap_1, trigger_handicap_1 = get_emoji_for_bet(handicap_bet_1)

    # Если хотя бы один триггер сработал для первой конторы
    trigger_bk_0 = trigger_total_0 or trigger_total_1 or trigger_handicap_0 or trigger_handicap_1

    table = (
        f"<b>{opponent_0.upper()} vs {opponent_1.upper()}</b>\n"
        f"{content['time_game']}\n"
        "-----------------------------------------------\n"
        f"<b>{site}</b>\n"
        f"Total: {content['total_point']}|{total_bet_0} {emoji_total_0}|{total_bet_1} {emoji_total_1}\n"
        f"Handi: {content['handicap_point_0']}|{handicap_bet_0} {emoji_handicap_0}|{content['handicap_point_1']}|{handicap_bet_1} {emoji_handicap_1}\n"
    )

    # Проверка коэффициентов для второй букмекерской конторы (content_2), если она передана
    if content_2:
        site_2_total_bet_0 = float(content_2.get('total_bet_0', '0'))
        site_2_total_bet_1 = float(content_2.get('total_bet_1', '0'))
        site_2_handicap_bet_0 = float(content_2.get('handicap_bet_0', '0'))
        site_2_handicap_bet_1 = float(content_2.get('handicap_bet_1', '0'))
        site_2 = content_2['site']

        # Проверка коэффициентов для второй букмекерской конторы
        emoji_total_0_2, trigger_total_0_2 = get_emoji_for_bet(site_2_total_bet_0)
        emoji_total_1_2, trigger_total_1_2 = get_emoji_for_bet(site_2_total_bet_1)
        emoji_handicap_0_2, trigger_handicap_0_2 = get_emoji_for_bet(site_2_handicap_bet_0)
        emoji_handicap_1_2, trigger_handicap_1_2 = get_emoji_for_bet(site_2_handicap_bet_1)

        # Если хотя бы один триггер сработал для второй конторы
        trigger_bk_1 = trigger_total_0_2 or trigger_total_1_2 or trigger_handicap_0_2 or trigger_handicap_1_2

        table += (
            "-----------------------------------------------\n"
            f"<b>{site_2}</b>\n"
            f"Total: {content['total_point']}|{site_2_total_bet_0} {emoji_total_0_2}|{site_2_total_bet_1} {emoji_total_1_2}\n"
            f"Handi: {content['handicap_point_0']}|{site_2_handicap_bet_0} {emoji_handicap_0_2}|{content['handicap_point_1']}|{site_2_handicap_bet_1} {emoji_handicap_1_2}\n"
        )


    try:

        if liga:
            if liga == 'IPBL Pro Division':
                if opponent_0 in IPBL1_TEAMS:
                    await bot.send_message(
                        chat_id=TG_CHAT_IPBL1,
                        text=table,
                        parse_mode='HTML'
                    )
                else:
                    await bot.send_message(
                        chat_id=TG_CHAT_IPBL2,
                        text=table,
                        parse_mode='HTML'
                    )
            else:
                await bot.send_message(chat_id=LEAGUES[liga], text=table, parse_mode='HTML')
    except TelegramError as e:
        print(f"Ошибка при отправке сообщения: {e}")

    # Если триггеры сработали для обеих контор, добавляем сообщение "ALARM"
    if trigger_bk_0 and trigger_bk_1:
        table += "\n‼️‼️‼️<b>ALARM</b>‼️‼️‼️\n"
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=table,
            parse_mode='HTML'
        )
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=table, parse_mode='HTML')
