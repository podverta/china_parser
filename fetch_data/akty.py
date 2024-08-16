import os
import re
import copy
import asyncio
import socketio
import hashlib
import traceback
import json
import time
import undetected_chromedriver as uc
from typing import List, Dict, Any
from translatepy import Translator
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from app.logging import setup_logger
from transfer_data.redis_client import RedisClient
from transfer_data.telegram_bot import send_message_to_telegram
from scripts.translate_cash_load import load_translate_cash, save_translate_cash


# Загрузка переменных окружения из .env файла
load_dotenv()
# Настройка логгера
logger = setup_logger('akty', 'akty_debug.log')
LOCAL_DEBUG = 0
LEAGUES = {
    'IPBL篮球专业组': 'IPBL Pro Division',
    'IPBL女子篮球专业组': 'IPBL Pro Division Women',
    '火箭篮球联盟': 'Rocket Basketball League',
    '火箭女子篮球联盟': 'Rocket Basketball League Women',
}

PROXY = os.getenv('PROXY')
URL = os.getenv('AKTY_URL')
LOGIN = os.getenv('AKTY_LOGIN')
PASSWORD = os.getenv('AKTY_PASSWORD')
NAME_BOOKMAKER = 'akty.com'
REDIS_URL = os.getenv('REDIS_URL')
SOCKETIO_URL = os.getenv('SOCKETIO_URL')
SOCKET_KEY = os.getenv('SOCKET_KEY')
HEADLESS = True


class FetchAkty:
    def __init__(
            self,
            url=URL,
            proxy=PROXY
    ):
        """
        Инициализация класса FetchAkty. Устанавливает URL
        и инициализирует WebDriver.
        """
        self.url = url
        self.proxy = proxy
        self.sio = socketio.AsyncSimpleClient()
        self.redis_client = None
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
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
        self.translate_cash = None
        self.action = ActionChains(self.driver)
        self.previous_data = {}
        self.translator = Translator()
        self.translate_cash = load_translate_cash()

    async def save_games(self, data: dict, liga_name: str):
        """
        Сохраняет игры по отдельным ключам в Redis.

        Args:
            data (dict): Данные в формате JSON для сохранения.
            liga_name (str): Наименование лиги для сохранения в redis.
        """
        try:
            rate_bets = [
                'total_bet_0',
                'total_bet_1',
                'handicap_bet_0',
                'handicap_bet_1'
            ]
            data_rate = data.get('rate', {})

            def safe_float(value):
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None

            # Проверяем, нужно ли сохранять данные в Redis
            is_save = any(
                safe_float(data_rate.get(rate_bet, '0')) is not None and
                safe_float(data_rate.get(rate_bet, '0')) <= 1.73
                for rate_bet in rate_bets
            )
            if is_save:
                opponent_0 = data.get('opponent_0', '')
                opponent_1 = data.get('opponent_1', '')
                key = (f"akty.com, {liga_name.lower()}, "
                       f"{opponent_0.lower()}, {opponent_1.lower()}")

                data_rate['server_time'] = data.get('server_time', '')
                json_data = json.dumps(data_rate, ensure_ascii=False)
                if not self.debug:
                    await self.redis_client.add_to_list(key, json_data)

                # Проверяем, нужно ли отправить данные в Telegram
                is_send_tg = any(
                    safe_float(data_rate.get(rate_bet, '0')) is not None and
                    safe_float(data_rate.get(rate_bet, '0')) <= 1.68
                    for rate_bet in rate_bets
                )
                if is_send_tg:
                    data_rate['opponent_0'] = opponent_0
                    data_rate['opponent_1'] = opponent_1
                    data_rate['liga'] = liga_name
                    data_rate['site'] = 'OB'
                    await send_message_to_telegram(data_rate)

        except Exception as e:
            await self.send_to_logs(f'Ошибка при сохранении данных: {str(e)}')

    async def send_data(
            self,
            data: dict
    ):
        """
        Отправка данных на Socket.IO сервер и сохранение в Redis.

        :param data: Данные для отправки и сохранения.
        """

        if self.debug:
            await self.send_to_logs(
                "Режим отладки включен, данные не отправляются."
            )
            await self.send_to_logs(
                f'{data}'
            )
            return
        try:
            json_data = json.dumps(data, ensure_ascii=False)
            # Отправляем данные на Socket.IO сервер напрямую
            await self.sio.emit('message', json_data)
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
                f"Connecting to Socket.IO server at {SOCKETIO_URL}"
            )
            if not self.sio.connected:
                await self.sio.connect(SOCKETIO_URL,
                                   auth={'socket_key': SOCKET_KEY})
        except Exception as e:
            print(f"Error initializing async components: {e}")
            raise

    async def get_driver(
            self,
            headless: bool = False,
            retries: int = 3
    ) -> uc.Chrome:
        """
        Инициализирует и возвращает WebDriver для браузера Chrome.

        :param headless: Запуск браузера в headless режиме.
        :param retries: Количество попыток запуска WebDriver в случае ошибки.
        :return: WebDriver для браузера Chrome.
        """
        options = uc.ChromeOptions()
        if self.proxy:
            options.add_argument(f'--proxy-server={self.proxy}')

        attempt = 0
        while attempt < retries:
            try:
                driver = uc.Chrome(options=options, headless=headless)
                return driver
            except WebDriverException as e:
                attempt += 1
                logger.error(
                    f"Ошибка при запуске драйвера "
                    f"(попытка {attempt} из {retries}): {e}")
                if attempt >= retries:
                    raise e
                await asyncio.sleep(5)

    async def get_url(
            self,
            url: str
    ):
        """
        Загружает основную страницу по заданному URL.

        :param url: URL страницы для загрузки.
        """
        self.driver.get(url)

    async def scroll_to_element(
            self,
            element: WebElement
    ) -> None:
        """
        Прокручивает страницу до указанного элемента,
         чтобы он оказался по центру экрана.

        :param element: WebElement, до которого необходимо прокрутить страницу.
        """
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
            element)

    async def scroll_to_bottom(
            self,
            wait_time: int = 5
    ) -> None:
        """
        Аккуратно прокручивает страницу до низа,
        ожидая указанное количество секунд.

        :param wait_time: Время ожидания в секундах перед началом прокрутки.
        """
        await asyncio.sleep(wait_time)
        scroll_pause_time = 0.1  # Уменьшенная пауза  для плавности
        scroll_step = 100  # Количество пикселей для каждой прокрутки

        last_height = self.driver.execute_script(
            "return document.body.scrollHeight")

        while True:
            self.driver.execute_script("window.scrollBy(0, arguments[0]);",
                                       scroll_step)
            await asyncio.sleep(scroll_pause_time)
            new_height = self.driver.execute_script(
                "return document.body.scrollHeight")

            if new_height == last_height:
                break
            last_height = new_height

    async def wait_for_element(
            self,
            by: By,
            value: str,
            timeout: int = 10
    ) -> WebElement:
        """
        Ожидает загрузки элемента на странице по заданным критериям.

        :param by: Стратегия поиска элемента (например, By.CSS_SELECTOR).
        :param value: Значение для поиска элемента.
        :param timeout: Время ожидания в секундах (по умолчанию 10 секунд).
        :return: Найденный элемент или None,
        если элемент не был найден в течение заданного времени.
        """
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            # Проверяем наличие элемента с сообщением о входе в другой сессии
            if await self.is_logged_in_elsewhere():

                await self.send_to_logs(
                    "Обнаружено сообщение о входе в другом месте. Перезапуск парсера."
                )
                await self.run()

            return element
        except TimeoutException:
            print(
                f"Элемент {by} {value} не был загружен в"
                f" течение заданного времени")
            if not self.debug:
                await self.sio.disconnect()
                self.driver.quit()
            else:
                breakpoint()

    async def is_logged_in_elsewhere(self) -> bool:
        """
        Проверяет, отображается ли на странице сообщение о входе в другом месте.

        :return: True, если сообщение отображается, иначе False.
        """
        try:
            message_element = self.driver.find_element(By.CSS_SELECTOR,
                                                       ".ant-mowin-s2-messageBox")
            if message_element and "账户在其它地方登录" in message_element.text:
                print(message_element.text())
                return True
        except NoSuchElementException:
            return False
        return False

    async def send_to_logs(
            self,
            message: str,
    ):
        """
        Отправляет сообщение в логгер и выводит его в консоль.

        :param message: Сообщение для логгера.
        """
        if not self.debug:
            logger.info(message)
        print(f"Logger: {message}")

    async def check_changed_dict(
            self,
            existing_list: List[Dict[str, Any]],
            game_info: Dict[str, Any],
            liga_name: str
    ) -> bool:
        """
        Проверяет и обновляет список словарей, если конкретный словарь изменился, или добавляет его, если его нет.

        :param existing_list: Список существующих словарей.
        :param game_info: Новый словарь для добавления или обновления.
        :param liga_name: Наименование лиги.
        :return: True, если данные изменились и были сохранены, иначе False.
        """
        new_dict = copy.deepcopy(game_info)
        for existing_dict in existing_list:
            if (existing_dict['opponent_0'] == new_dict['opponent_0'] and
                    existing_dict['opponent_1'] == new_dict['opponent_1']):
                if existing_dict['rate'] != new_dict['rate']:
                    await self.save_games(new_dict, liga_name)
                    return True
                return False
        return True

    async def authorization(
            self
    ) -> None:
        """
        Авторизация на странице.
        """
        await self.get_url(self.url)
        login_input = await self.wait_for_element(By.CSS_SELECTOR,
                                            "input[placeholder*='账号']",
                                            timeout=60)
        await asyncio.sleep(15)
        login_input.send_keys(LOGIN)
        password_input = await self.wait_for_element(By.CSS_SELECTOR,
                                               "input[placeholder='密码']")
        password_input.clear()
        password_input.send_keys(PASSWORD)
        password_input.send_keys(Keys.ENTER)
        await self.send_to_logs('Авторизация успешно пройдена')

    async def translate_and_cache(
            self,
            text: str
    ) -> str:
        """
        Перевод строки на Русский язык.
        """
        try:
            if not text:
                return text
            sanitized_name = text.translate(str.maketrans('', '', ' (),女')).lower()
            for key in self.translate_cash:
                if key in sanitized_name:
                    return self.translate_cash[key]

            translation = self.translator.translate(sanitized_name, "english").result
            self.translate_cash = load_translate_cash()
            self.translate_cash[sanitized_name] = translation.lower()
            save_translate_cash(self.translate_cash)
            await self.send_to_logs(
                f"Перевод текста: '{sanitized_name}' перевод: '{translation}'")

            return translation

        except Exception as e:
            await self.send_to_logs(
                f"Ошибка при переводе: {e}, текст: '{sanitized_name}'")
            return text

    async def main_page(
            self
    ) -> None:
        """
        Переход с главной страницы.
        """
        """
        Загружает основную страницу по заданному URL с проверкой на элемент загрузки.
        """
        max_retries = 3

        for attempt in range(max_retries):
            try:
                await asyncio.sleep(5)
                ul_element = await self.wait_for_element(
                    By.CLASS_NAME,
                    "header__venue__3IZlT",
                    timeout=30
                )
                if ul_element:
                    span_element = ul_element.find_element(
                        By.XPATH,
                        ".//span[text()='体育']"
                    )
                    self.action.move_to_element(span_element).perform()
                    await asyncio.sleep(2)

                    # Проверка кликабельности элемента
                    h4_element = await self.wait_for_element(
                        By.XPATH,
                        "//img[@src='https://senbackkg.m42i79a.com/main-consumer-web/assets-oss/ak/images/header/ty-hq.fcfac2c0d9d469709a1ede2e376bf482.webp?x-oss-process=image/resize,w_210,h_210/quality,Q_100/sharpen,100/format,webp']"
                    )

                    if h4_element.is_displayed() and h4_element.is_enabled():
                        h4_element.click()
                        return
                    else:
                        # Если элемент не кликабелен, перезагружаем страницу и повторяем
                        self.driver.refresh()
                        await asyncio.sleep(5)
                        continue
                else:
                    self.driver.refresh()
                    await asyncio.sleep(5)
                    continue

            except Exception as e:
                logger.error(
                    f"Попытка {attempt + 1}/{max_retries} не удалась: {str(e)}")
                if attempt < max_retries - 1:
                    self.driver.refresh()
                    await asyncio.sleep(5)
                else:
                    raise e

    async def aggregator_page(
            self
    ) -> None:
        """
        Переход на страницу агрегатора.
        """
        copyright_paragraph = await self.wait_for_element(
            By.CSS_SELECTOR,
            "p[class*='style__copyright']",
            timeout=30
        )
        await self.scroll_to_element(copyright_paragraph)
        await self.send_to_logs('Успешный вход в систему')
        iframe_element = await self.wait_for_element(
            By.CSS_SELECTOR,
            "iframe[title='venuIframe']",
            timeout=60
        )
        await asyncio.sleep(20)
        self.driver.switch_to.frame(iframe_element)
        basketball_element = await self.wait_for_element(By.CSS_SELECTOR,
                                                   "span[alt='篮球']",
                                                   timeout=15)
        if basketball_element:
            basketball_element.click()
        else:
            window_size = self.driver.get_window_size()
            window_width = window_size['width']
            # Вычисляем координаты для клика в правый верхний угол
            right_upper_x = window_width - 1  # 1 пиксель левее правой границы
            right_upper_y = 1
            self.actions.move_by_offset(right_upper_x, right_upper_y).click().perform()
            await self.aggregator_page()

        await self.send_to_logs('Успешный переход в раздел баскетбола')

    async def change_zoom(
            self
    ):
        self.driver.get('chrome://settings/appearance')
        self.driver.execute_script(
            'chrome.settingsPrivate.setDefaultZoom(0.25);'
        )

    async def get_content(
            self
    ):
        """
        Получение контента с страницы с 5 попытками.

        :return: Объект BeautifulSoup с содержимым HTML или None, если контент не найден.
        """
        max_attempts = 6
        attempt = 0

        while attempt < max_attempts:
            element = await self.wait_for_element(
                By.CSS_SELECTOR,
                "div[class*='v-scroll-content relative-position']",
                timeout=30
            )

            if element:
                html = element.get_attribute('outerHTML')
                soup = BeautifulSoup(html, 'html.parser')
                return soup
            logger.info(
                f"Внимание! Отсутствие контента на странице,"
                f" Попытка {attempt + 1} из {max_attempts} получить контент.")
            attempt += 1
            await asyncio.sleep(
                30)

        await self.send_to_logs(
            'Остановка парсера, не найден <div> с играми после 5 попыток.'
        )
        await self.sio.disconnect()
        self.driver.quit()
        return None

    async def get_container_hash(self) -> str:
        """
        Получение хэш-суммы контейнера с играми.
        :return: str
        """
        soup = await self.get_content()

        if not soup:
            return ''
        return hashlib.md5(str(soup).encode('utf-8')).hexdigest()

    async def click_element_by_text(self) -> None:
        try:
            spoiler_button = await self.wait_for_element(By.CSS_SELECTOR,"div[class*='match-type']",timeout=30)
            spoiler_button.click()
            await asyncio.sleep(1)
            spoiler_button.click()
            await self.send_to_logs(
                'Переключение видимости лиг произошло успешно'
            )
        except Exception as e:
            await self.send_to_logs(
                f'При переключении произошла ошибка: {e}'
            )
            await self.run()

    async def extract_league_data(
            self,
            target_leagues: dict
    ) -> dict:
        """
        Извлечение данных лиг из HTML.
        :param target_leagues: dict
        :return: dict
        """
        soup = await self.get_content()
        leagues_data = {NAME_BOOKMAKER: {}}
        previous_leagues_data = {NAME_BOOKMAKER: {}}
        scroll_content = soup.find('div',
                                   class_='v-scroll-content relative-position')

        if not scroll_content:
            return leagues_data

        cards = scroll_content.find_all(
            'div',
            class_=re.compile(
                'list-card-wrap 1 v-scroll-item 1 relative-position'),
            recursive=False
        )

        league_name = None
        for card in cards:
            div_name_liga = card.find('span',
                                      class_="ellipsis allow-user-select")
            if div_name_liga:
                league_name = div_name_liga.get_text()
                if league_name in target_leagues.keys():
                    if 'style' in card.attrs and re.search(r'height:\s*37px;',
                                                           card['style']):
                        await self.click_element_by_text()
            elif league_name and league_name in target_leagues.keys():
                league_name = target_leagues[league_name]
                list_mid_elements = card.find_all('div',
                                                  id='list-mid-undefined')
                for list_mid_element in list_mid_elements:
                    opponent_0 = list_mid_element.find('div',
                                                       class_='row-item team-item')
                    opponent_1 = list_mid_element.find('div',
                                                       class_='row-item team-item soon')

                    if opponent_0 and opponent_1:
                        opponent_0_name = opponent_0.find('div',
                                                          class_=re.compile(
                                                              'allow-user-select')).get_text()
                        translate_opponent_0_name = await self.translate_and_cache(
                            opponent_0_name) if opponent_0_name != '' else ''
                        opponent_1_name = opponent_1.find('div',
                                                          class_=re.compile(
                                                              'allow-user-select')).get_text()
                        translate_opponent_1_name = await self.translate_and_cache(
                            opponent_1_name) if opponent_1_name != '' else ''

                        opponent_0_score_div = opponent_0.find('div',
                                                               class_='score')
                        opponent_0_score = opponent_0_score_div.find(
                            'span').get_text() if opponent_0_score_div else ""
                        opponent_1_score_div = opponent_1.find('div',
                                                               class_='score')
                        opponent_1_score = opponent_1_score_div.find(
                            'span').get_text() if opponent_1_score_div else ""

                        bet_divs = card.find_all('div', class_='handicap-col')
                        handicap_bet_div = bet_divs[1].find_all('span',
                                                                class_='highlight-odds')
                        handicap_point_divs = bet_divs[1].find_all('div',
                                                                   class_='handicap-value-text handicap-value-ranks')

                        opponent_0_handicap_bet = handicap_bet_div[
                            0].get_text() if len(handicap_bet_div) > 0 else ""
                        opponent_0_handicap_point = handicap_point_divs[
                            0].get_text().strip() if len(
                            handicap_point_divs) > 0 else ""
                        opponent_1_handicap_bet = handicap_bet_div[
                            1].get_text() if len(handicap_bet_div) > 1 else ""
                        opponent_1_handicap_point = handicap_point_divs[
                            1].get_text().strip() if len(
                            handicap_point_divs) > 1 else ""

                        total_bet_div = bet_divs[2].find_all('span',
                                                             class_='highlight-odds')
                        total_point_divs = bet_divs[2].find_all('div',
                                                                class_='handicap-value-text handicap-value-ranks')

                        opponent_0_total_bet = total_bet_div[
                            0].get_text() if len(total_bet_div) > 0 else ""
                        opponent_0_total_point = total_point_divs[
                            0].get_text().strip() if len(
                            total_point_divs) > 0 else ""
                        opponent_1_total_bet = total_bet_div[
                            1].get_text() if len(total_bet_div) > 1 else ""

                        process_time_span = list_mid_element.find('span',
                                                                  class_='timer-layout2')
                        process_time = process_time_span.get_text() if process_time_span else ""

                        process_time_div_text = list_mid_element.find('div',
                                                                      class_='process_name')
                        process_time_text = self.time_game_translate.get(
                            process_time_div_text.get_text().strip(),
                            ''
                        ) if process_time_div_text else ""

                        server_time = datetime.now(
                            tz=ZoneInfo("Europe/Moscow")).strftime("%H:%M:%S")

                        game_info = {
                            'opponent_0': translate_opponent_0_name,
                            'opponent_1': translate_opponent_1_name,
                            'score_game': f'{opponent_0_score}:{opponent_1_score}',
                            'time_game': f'{process_time_text} {process_time}',
                            'rate': {
                                'total_point': opponent_0_total_point,
                                'total_bet_0': opponent_0_total_bet,
                                'total_bet_1': opponent_1_total_bet,
                                'handicap_point_0': opponent_0_handicap_point,
                                'handicap_bet_0': opponent_0_handicap_bet,
                                'handicap_point_1': opponent_1_handicap_point,
                                'handicap_bet_1': opponent_1_handicap_bet,
                            },
                            'server_time': server_time,
                        }

                        if league_name not in leagues_data[NAME_BOOKMAKER]:
                            leagues_data[NAME_BOOKMAKER][league_name] = []
                            previous_leagues_data[NAME_BOOKMAKER][
                                league_name] = []

                        if (
                                self.previous_data and league_name in self.previous_data.get(
                                NAME_BOOKMAKER, {})):
                            changed_data = await self.check_changed_dict(
                                self.previous_data[NAME_BOOKMAKER][league_name],
                                game_info,
                                league_name
                            )
                            if changed_data:
                                leagues_data[NAME_BOOKMAKER][
                                    league_name].append(game_info)

                        previous_leagues_data[NAME_BOOKMAKER][
                                league_name].append(game_info)

        self.previous_data = previous_leagues_data
        leagues_data[NAME_BOOKMAKER] = {
            k: v for k, v in leagues_data[NAME_BOOKMAKER].items() if v
        }
        if any(leagues_data[NAME_BOOKMAKER].values()):
            return leagues_data

    async def monitor_leagues(
            self,
            target_leagues: dict,
            check_interval: int = 1
    ) -> None:
        """
        Мониторинг данных лиг.

        :param target_leagues: list
        :param check_interval: int
        """
        previous_hash = await self.get_container_hash()
        while True:
            await asyncio.sleep(check_interval)
            current_hash = await self.get_container_hash()

            if current_hash != previous_hash:
                try:
                    leagues_data = await self.extract_league_data(
                        target_leagues
                    )
                    previous_hash = current_hash
                    if leagues_data:
                        await self.send_data(leagues_data)
                except Exception:
                    await self.send_to_logs(
                        f'Ошибка: {traceback.format_exc()}'
                    )
            else:
                await self.send_to_logs(
                    "Данные не изменились."
                )

    async def close(self):
        if self.driver:
            self.driver.quit()
            await self.send_to_logs("Драйвер был закрыт принудительно")
        if self.redis_client:
            await self.redis_client.close()

    def __del__(self):
        asyncio.run(self.close())

    async def run(self, *args, **kwargs):
        """
        Запуск парсера с указанными параметрами и перезапуском при ошибках.

        Args:
            *args: Позиционные аргументы.
            **kwargs: Именованные аргументы.
        """
        leagues = kwargs.get('leagues', LEAGUES)
        attempt = 0
        max_retries = 5

        while attempt < max_retries:
            try:
                if not self.debug:
                    self.redis_client = RedisClient()
                    await self.redis_client.connect()
                await self.change_zoom()
                await self.init_async_components()
                await self.authorization()
                await self.main_page()
                await self.aggregator_page()
                await self.monitor_leagues(leagues)
                break  # Успешное выполнение, выход из цикла
            except Exception as e:
                if self.driver and self.driver.session_id:
                    self.driver.save_screenshot(
                        f'screenshot_akty_{attempt}.png')
                await self.send_to_logs(
                    f"Произошла ошибка: {str(e)}. Попытка {attempt + 1} из {max_retries}.")
                await asyncio.sleep(10)
                attempt += 1
                if attempt >= max_retries:
                    await self.send_to_logs(
                        "Достигнуто максимальное количество попыток. Остановка.")
                    break
            finally:
                await self.redis_client.close()
                self.driver.quit()



if __name__ == "__main__":
    LOCAL_DEBUG = 1
    HEADLESS = False
    fetch_akty = FetchAkty()
    asyncio.run(fetch_akty.run())
