import time
import os
import re
import socketio
import json
import asyncio
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from googletrans import Translator
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from app.logging import setup_logger
from selenium.webdriver.common.action_chains import ActionChains
from transfer_data.redis_client import RedisClient

# Загрузка переменных окружения из .env файла
load_dotenv()
URL = "https://test.f66b88sport.com/pc/index.html#/"

LEAGUES = {
    'IPBL篮球专业组': 'IPBL Pro Division',
    'IPBL女子篮球专业组': 'IPBL Pro Division Women',
    '火箭篮球联盟': 'Rocket Basketball League',
    '火箭女子篮球联盟': 'Rocket Basketball League Women',
}
LOCAL_DEBUG = 0
REDIS_URL = os.getenv('REDIS_URL')
SOCKETIO_URL = os.getenv('SOCKETIO_URL')
SOCKET_KEY = os.getenv('SOCKET_KEY')
HEADLESS = True

# Настройка логгера
logger = setup_logger('fb', 'fb_debug.log')


class OddsFetcher:
    def __init__(
            self
    ):
        """
        Инициализация класса OddsFetcher.
        Устанавливает URL и инициализирует WebDriver.

        :param url: URL страницы для загрузки.
        :param leagues: Список целевых лиг.
        :param headless: Запуск браузера в headless режиме.
        """
        self.url = URL
        self.loop = asyncio.new_event_loop()
        self.sio = socketio.AsyncSimpleClient()
        asyncio.set_event_loop(self.loop)
        self.redis_client = None
        self.driver = self.loop.run_until_complete(
            self.get_driver(headless=HEADLESS)
        )
        self.time_game_translate = {
            '第一节': 'I',
            '第二节': 'II',
            '第三节': 'III',
            '第四节': 'IV'
        }
        self.debug = LOCAL_DEBUG
        self.actions = None
        self.translate_cash = {}
        self.translator = Translator()
        self.previous_data = {}

    async def get_driver(
            self,
            headless: bool = False,
            ) -> None:
        """
        Инициализирует и возвращает WebDriver для браузера Chrome.
        :param headless: Запуск браузера в headless режиме.
        """
        return uc.Chrome(options=uc.ChromeOptions(), headless=headless)

    async def get_url(self):
        """
        Загружает основную страницу по заданному URL с проверкой на элемент загрузки.
        """
        max_retries = 3
        wait_time = 10  # Время ожидания для исчезновения элемента

        for attempt in range(max_retries):
            try:
                # Очистка кеша и cookies
                self.driver.delete_all_cookies()

                # Перезагрузка страницы
                self.driver.get(self.url)

                # Явное ожидание появления и исчезновения элемента загрузки
                try:
                    WebDriverWait(self.driver, wait_time).until(
                        EC.presence_of_element_located((
                            By.CSS_SELECTOR,
                            'div.q-loading.fullscreen.column.flex-center.z-max.text-black'
                        ))
                    )

                    # Дополнительное ожидание исчезновения элемента
                    WebDriverWait(self.driver, wait_time).until_not(
                        EC.visibility_of_element_located((
                            By.CSS_SELECTOR,
                            'div.q-loading.fullscreen.column.flex-center.z-max.text-black'
                        ))
                    )

                    # Логируем успешную загрузку
                    await self.send_to_logs(
                        f"Элемент загрузки исчез, страница загружена {self.url} "
                        f"(попытка {attempt + 1})"
                    )
                    break  # Элемент загрузки исчез, продолжаем выполнение

                except TimeoutException:
                    # Элемент загрузки не исчез
                    await self.send_to_logs(
                        f"Элемент загрузки не исчез на странице {self.url}, "
                        f"перезагрузка страницы... (попытка {attempt + 1})"
                    )

                    # Явное обновление страницы
                    self.driver.refresh()
                    await asyncio.sleep(5)  # Ожидание перед повторной попыткой
                    continue  # Перезагрузка страницы и повторная попытка

            except Exception as e:
                await self.send_to_logs(
                    f"Произошла ошибка: {e}. Попытка {attempt + 1} из {max_retries}."
                )
                if attempt + 1 >= max_retries:
                    raise e
                await asyncio.sleep(5)  # Ожидание перед повторной попыткой

        else:
            await self.send_to_logs(
                f"Не удалось загрузить страницу без элемента загрузки после {max_retries} попыток"
            )
            raise Exception(
                "Не удалось загрузить страницу без элемента загрузки.")

    async def save_games(self, data: dict):
        """
        Сохраняет игры по отдельным ключам в Redis.

        Args:
            data (dict): Данные в формате JSON для сохранения.
        """
        try:
            # Перемещение по JSON-объекту
            for site, leagues in data.items():
                for league, games in leagues.items():
                    for game in games:
                        opponent_0 = game["opponent_0"]
                        opponent_1 = game["opponent_1"]

                        # Формируем ключ
                        key = (f"{site.lower()}, {league.lower()}, "
                               f"{opponent_0.lower()}, {opponent_1.lower()}")

                        # Преобразуем данные в JSON
                        json_data = json.dumps(game, ensure_ascii=False)

                        # Сохраняем данные в Redis
                        await self.redis_client.add_to_list(key, json_data)
                        await self.send_to_logs(f'Сохранение данных: {key} - {json_data}')
        except Exception as e:
            await self.send_to_logs(f'Ошибка при сохранении данных: {str(e)}')

    async def send_and_save_data(
            self,
            data: dict,
    ):
        """
        Отправка данных на Socket.IO сервер и сохранение в Redis.

        :param data: Данные для отправки и сохранения.
        """
        self.previous_data = data
        if self.debug:
            await self.send_to_logs(
                "Режим отладки включен, данные не отправляются."
            )
            return
        try:
            json_data = json.dumps(data, ensure_ascii=False)
            # Отправляем данные на Socket.IO сервер напрямую
            await self.sio.emit('message', json_data)
            # Сохраняем данные в Redis
            await self.save_games(data)
        except Exception as e:
            await self.send_to_logs(f'Ошибка при отправке данных: {str(e)}')

    async def init_async_components(self):
        """
        Инициализация асинхронных компонентов, таких как Redis клиент и подключение к Socket.IO.
        """
        if self.debug:
            return None
        try:
            await self.send_to_logs(
                f"Connecting to Redis at {REDIS_URL}"
            )
            await self.send_to_logs(
                f"Connecting to Socket.IO server at {SOCKETIO_URL}"
            )
            await self.sio.connect(SOCKETIO_URL, auth={'socket_key': SOCKET_KEY})
            data_str = await self.redis_client.get_data('translate_cash')
            if data_str:
                self.translate_cash = json.loads(data_str.decode('utf-8'))
        except Exception as e:
            print(f"Error initializing async components: {e}")
            raise

    async def send_to_logs(
            self,
            message: str
    ):
        """
        Логирование сообщений.

        :param message: Сообщение для логирования.
        """
        if not self.debug:
            logger.info(message)
        print(f"Logger: {message}")

    async def wait_for_element(
            self,
            by: By,
            value: str,
            timeout: int = 10,
    ) -> WebElement:
        """
        Ожидает загрузки элемента на странице по заданным критериям.

        :param by: Стратегия поиска элемента (например, By.CSS_SELECTOR).
        :param value: Значение для поиска элемента.
        :param timeout: Время ожидания в секундах (по умолчанию 10 секунд).
        :param is_debug: Для остановки во время отладки.
        :return: Найденный элемент или None,
        если элемент не был найден в течение заданного времени.
        """
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR,
                     '.ui-carousel-item.sport-type-item img[src="sport-svg/sport_id_3.svg"]'))
            )

            return element
        except TimeoutException:
            return None

    async def main_page(
            self
    ) -> None:
        max_attempts = 6
        attempt = 0

        basketball_button = await self.wait_for_element(
            By.CSS_SELECTOR,
            '.ui-carousel-item.sport-type-item img[src="sport-svg/sport_id_3.svg"]',
            timeout=30
        )
        if basketball_button:
            basketball_button.click()
            await self.send_to_logs('Успешный переход в баскетбольную лигу')
            return
        logger.info(
            f"Внимание! Отсутствие контента на странице,"
            f" Попытка {attempt + 1} из {max_attempts} получить контент.")
        attempt += 1
        await asyncio.sleep(
            10)
        if attempt < max_attempts:
            await self.main_page()
        await self.send_to_logs(
            'Остановка парсера, не найден <div> с играми после 5 попыток.'
        )
        await self.sio.disconnect()
        self.driver.quit()

    async def get_translate(
            self,
            short_name: str
    ) -> str:
        """
        Получает полное название команды, используя кэш или выполнив наведение на элемент.
        """
        translation = ""
        if short_name in self.translate_cash.keys():
            return self.translate_cash[short_name]
        time.sleep(1)
        team1_element = self.driver.find_element(By.XPATH, f"//*[text()='{short_name}']")
        if self.actions is None:
            self.actions = ActionChains(self.driver)
        self.actions.move_to_element(team1_element).perform()
        time.sleep(2)
        full_name_element = self.driver.execute_script("""
                   var tooltip = document.querySelector('div[role="complementary"].q-tooltip--style.q-position-engine.no-pointer-events[style*="visibility: visible"]');
                   if (tooltip) {
                       return tooltip.textContent.trim();
                   } else {
                       return null;
                   }
               """)
        if full_name_element:
            translation = self.translator.translate(
                full_name_element, src='zh-cn',
                dest='en'
            ).text
        if translation:
            self.translate_cash[short_name] = translation
            if self.debug:
                return translation
            json_data = json.dumps(self.translate_cash, ensure_ascii=False)
            await self.redis_client.set_data('translate_cash', json_data)
            await self.send_to_logs(f"Перевод текста {short_name}"
                                    f" - {translation}")
            return translation
        return None

    @staticmethod
    async def check_changed_dict(
            existing_list: List[Dict[str, Any]],
            new_dict: Dict[str, Any],
    ) -> Dict:
        """
        Обновляет список словарей, если конкретный словарь изменился, или добавляет его, если его нет.

        Args:
            existing_list (List[Dict[str, Any]]): Список существующих словарей.
            new_dict (Dict[str, Any]): Новый словарь для добавления или обновления.

        Returns:
            List[Dict[str, Any]]: Обновленный список словарей.
        """
        for i, existing_dict in enumerate(existing_list):
            if (existing_dict['opponent_0'] == new_dict['opponent_0'] and
                    existing_dict['opponent_1'] == new_dict['opponent_1']):
                if existing_dict['rate'] == new_dict['rate']:
                    new_dict['changed'] = False
        return new_dict

    async def collect_odds_data(
            self,
            target_leagues: dict,
    ):
        """
        Сбор данных о коэффициентах для заданных лиг.
        """
        active_matches = {"fb.com": {}}

        try:
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            match_groups = soup.select('.home-match-list-box .group-matches')
            for group in match_groups:
                league_name_element = group.select_one('.league-name')
                if league_name_element is None:
                    continue
                league_name = league_name_element.text
                if league_name in target_leagues:
                    if league_name not in active_matches["fb.com"]:
                        liga_name_translate = target_leagues[league_name]
                        active_matches["fb.com"][liga_name_translate] = []
                    matches = group.select(
                        '.home-match-list__item.home-match-info'
                    )
                    for match in matches:
                        team_names = match.select(
                            '.match-teams-name .team-name'
                        )
                        if len(team_names) != 2:
                            continue

                        short_team1_name = team_names[0].text.strip()
                        short_team2_name = team_names[1].text.strip()
                        translate_opponent_0_name = await self.get_translate(
                            short_team1_name) if short_team1_name != '' else ''
                        translate_opponent_1_name = await self.get_translate(
                            short_team2_name) if short_team1_name != '' else ''
                        scores = match.select('.match-score p span')
                        if len(scores) != 2:
                            continue
                        opponent_0_score = scores[0].text
                        opponent_1_score = scores[1].text
                        game_info = {
                            'changed': True,
                            'opponent_0': translate_opponent_0_name,
                            'opponent_1': translate_opponent_1_name,
                            'score_game': f'{opponent_0_score}:{opponent_1_score}',
                            'time_game': '',
                            'rate': {
                                'total_point': '',
                                'total_bet_0': '',
                                'total_bet_1': '',
                                'handicap_point_0': '',
                                'handicap_bet_0': '',
                                'handicap_point_1': '',
                                'handicap_bet_1': '',
                            },
                            'server_time': '',
                        }
                        process_time_elements = match.select('.time')
                        if process_time_elements:
                            process_time_text_element = process_time_elements[
                                0].select_one('.match-left-text.font-din')
                            process_time_text = self.time_game_translate.get(
                                process_time_text_element.get_text().strip(),
                                '') if process_time_text_element else ""
                            game_info['time_game'] += process_time_text

                            process_time_element = process_time_elements[
                                0].select_one('.match-left-time.font-din')

                            if process_time_element and process_time_element.text.strip():
                                process_time = process_time_element.text.strip()
                                game_info['time_game'] += ' ' + process_time
                        game_info['server_time'] = datetime.now(
                            tz=ZoneInfo("Europe/Moscow")
                        ).strftime("%H:%M:%S")
                        odds_boxes = match.select('.home-match-odds-box')
                        found_handicap = False
                        found_ou = False
                        for odds_box in odds_boxes:
                            category = odds_box.get('class', '')
                            if 'match-full-odds-handicap' in category and not found_handicap:
                                found_handicap = True
                                odds_items = odds_box.select('.team-odds-list .value.font-din')
                                if len(odds_items) >= 2:
                                    game_info['rate']['handicap_bet_0'] = odds_items[0].text
                                    game_info['rate']['handicap_bet_1'] = odds_items[1].text
                                handicap_points = odds_box.select('.team-odds-list .prefix-text.text-grey-disable')
                                if len(handicap_points) >=2:
                                    game_info['rate']['handicap_point_0'] = handicap_points[0].text
                                    game_info['rate']['handicap_point_1'] = handicap_points[1].text
                            elif ('match-full-odds-total' in category and
                                  not found_ou):
                                found_ou = True
                                odds_items = odds_box.select('.team-odds-list .value.font-din')
                                if len(odds_items) >= 2:
                                    game_info['rate']['total_bet_0'] = odds_items[0].text
                                    game_info['rate']['total_bet_1'] = odds_items[1].text
                                total_points = odds_box.select(
                                    '.team-odds-list .prefix-text.text-grey-disable')
                                if len(total_points) >= 2:
                                    point_0 = total_points[0].text
                                    point_0_cleared = re.sub(
                                        r'[大小 ]', '', point_0
                                    )
                                    game_info['rate'][
                                        'total_point'] = point_0_cleared if \
                                            point_0_cleared else \
                                            game_info['rate']['total_point']
                        if (self.previous_data and liga_name_translate
                                in self.previous_data.get("fb.com", {})):
                            odds_data = await self.check_changed_dict(
                                self.previous_data["fb.com"][liga_name_translate],
                                game_info,
                            )
                        active_matches["fb.com"][liga_name_translate].append(game_info)
            if self.debug:
                await self.send_to_logs(f'{active_matches}')
            await self.send_and_save_data(active_matches)

        except Exception as e:
            await self.send_to_logs(f"Произошла ошибка при сборе: {str(e)}")

    async def close(self):
        if self.driver:
            self.driver.quit()
            await self.send_to_logs("Драйвер был закрыт принудительно")
        if self.redis_client:
            await self.redis_client.close()

    def __del__(self):
        asyncio.run(fetcher.close())

    async def run(self, *args, **kwargs):
        """
        Основной метод для запуска парсера с перезапуском при ошибках.

        Args:
            *args: Позиционные аргументы.
            **kwargs: Именованные аргументы.
        """
        attempt = 0
        max_retries = 5

        while attempt < max_retries:
            try:
                self.redis_client = RedisClient()
                await self.redis_client.connect()
                await self.init_async_components()
                leagues = kwargs.get('leagues', LEAGUES)
                await self.get_url()
                await self.main_page()
                while True:
                    await self.collect_odds_data(leagues)
                    await asyncio.sleep(1)  # Пауза между циклами сбора данных
            except Exception as e:
                self.driver.save_screenshot(
                    f'screenshot_fb_{attempt}.png'
                )
                await self.send_to_logs(
                    f"Произошла ошибка: {str(e)}. "
                    f"Попытка {attempt + 1} из {max_retries}.")
                attempt += 1
                await asyncio.sleep(10)
                if attempt >= max_retries:
                    await self.send_to_logs(
                        "Достигнуто максимальное количество попыток. Остановка.")
                    break
            finally:
                self.driver.quit()
                await self.redis_client.close()

if __name__ == "__main__":
    LOCAL_DEBUG = 1
    HEADLESS = False
    fetcher = OddsFetcher()
    asyncio.run(fetcher.run())
