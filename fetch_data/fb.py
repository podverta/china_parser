import time
import os
import socketio
import json
import asyncio
import redis.asyncio as aioredis
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from googletrans import Translator
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from app.logging import setup_logger
from selenium.webdriver.common.action_chains import ActionChains

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
        self.redis_client = None
        self.debug = LOCAL_DEBUG
        self.actions = ActionChains(self.driver)
        self.translate_cash = {}
        self.translator = Translator()

    async def get_driver(self, headless: bool) -> webdriver.Chrome:
        """
        Инициализирует и возвращает WebDriver для браузера Chrome.
        :param headless: Запуск браузера в headless режиме.
        :return: WebDriver для браузера Chrome.
        """
        options = uc.ChromeOptions()
        driver = uc.Chrome(options=options, headless=headless)
        return driver

    async def get_url(self):
        """
        Загружает основную страницу по заданному URL.
        """
        self.driver.get(self.url)
        await self.send_to_logs(
            f"Переход на главную страницу выыполнен {self.url}"
        )
    async def send_and_save_data(
            self,
            data: dict,
    ):
        """
        Отправка данных на Socket.IO сервер и сохранение в Redis.

        :param data: Данные для отправки и сохранения.
        """
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
            await self.redis_client.set('akty_data', json_data)
        except Exception as e:
            await self.send_to_logs(f'Ошибка при отправке данных: {str(e)}')

    async def init_async_components(
            self
    ):
        """
        Инициализация асинхронных компонентов,
        таких как Redis клиент и подключение к Socket.IO.
        """
        if self.debug:
            return None
        try:
            await self.send_to_logs(
                f"Connecting to Redis at {REDIS_URL}"
            )
            self.redis_client = await aioredis.from_url(REDIS_URL)
            await self.send_to_logs(
                f"Connecting to Socket.IO server at {SOCKETIO_URL}"
            )
            await self.sio.connect(SOCKETIO_URL)
            data_str = await self.redis_client.get('translate_cash')
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
        while attempt < max_attempts:
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
                30)
        await self.send_to_logs(
            'Остановка парсера, не найден <div> с играми после 5 попыток.'
        )
        await self.sio.disconnect()
        self.driver.quit()

    async def get_full_team_name(
            self,
            short_name: str
    ) -> str:
        """
        Получает полное название команды, используя кэш или выполнив наведение на элемент.
        """
        if short_name in self.translate_cash.keys():
            return self.translate_cash[short_name]

        time.sleep(1)  # Подождем, чтобы всплывающее окно появилось
        data_str = await self.redis_client.get('translate_cash')
        if data_str:
            self.translate_cash = json.loads(data_str.decode('utf-8'))
        team1_element = self.driver.find_element(By.XPATH, f"//*[text()='{short_name}']")
        self.actions.move_to_element(team1_element).perform()
        time.sleep(2)  # Увеличиваем время ожидания

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
                dest='ru'
            ).text
            self.translate_cash[short_name] = translation
            if self.debug:
                return translation
            json_data = json.dumps(self.translate_cash, ensure_ascii=False)
            await self.redis_client.set('translate_cash', json_data)
            return full_name_element
        return None

    async def collect_odds_data(
            self,
            target_leagues: dict,
    ):
        """
        Сбор данных о коэффициентах для заданных лиг.
        """
        active_matches = {"fb.com": {}}

        try:
            time.sleep(1)
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            match_groups = soup.select('.home-match-list-box .group-matches')
            for group in match_groups:
                league_name_element = group.select_one('.league-name')
                if league_name_element is None:
                    continue
                league_name = league_name_element.text
                if league_name in target_leagues.keys():
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
                        full_team1_name = await self.get_full_team_name(
                            short_team1_name) if short_team1_name != '' else ''
                        full_team2_name = await self.get_full_team_name(
                            short_team2_name) if short_team1_name != '' else ''

                        scores = match.select('.match-score p span')
                        if len(scores) != 2:
                            continue

                        score1 = scores[0].text
                        score2 = scores[1].text

                        process_time_element = match.select_one(
                            '.match-left-time'
                        )
                        if process_time_element is None:
                            continue
                        process_time = process_time_element.text.strip()

                        server_time = datetime.now().strftime(
                            '%Y-%m-%d %H:%M:%S'
                        )

                        odds_data = {
                            'opponent_0': {
                                'name': full_team1_name,
                                'score': score1,
                                'handicap_bet': "",
                                'total_bet': ""
                            },
                            'opponent_1': {
                                'name': full_team2_name,
                                'score': score2,
                                'handicap_bet': "",
                                'total_bet': ""
                            },
                            'process_time': process_time,
                            'server_time': server_time
                        }

                        odds_boxes = match.select('.home-match-odds-box')
                        found_handicap = False
                        found_ou = False

                        for odds_box in odds_boxes:
                            category = odds_box.get('class', '')

                            if 'match-full-odds-handicap' in category and not found_handicap:
                                found_handicap = True
                                odds_items = odds_box.select('.team-odds-list .value.font-din')
                                if len(odds_items) >= 2:
                                    odds_data['opponent_0']['handicap_bet'] = (
                                        odds_items[0].text)
                                    odds_data['opponent_1']['handicap_bet'] = (
                                        odds_items[1].text)

                            elif ('match-full-odds-total' in category and
                                  not found_ou):
                                found_ou = True
                                odds_items = odds_box.select('.team-odds-list .value.font-din')
                                if len(odds_items) >= 2:
                                    odds_data['opponent_0']['total_bet'] = odds_items[0].text
                                    odds_data['opponent_1']['total_bet'] = odds_items[1].text
                        active_matches["fb.com"][liga_name_translate].append(odds_data)
            # await self.send_to_logs(
            #     f"Данные обновлены: {active_matches}"
            # )
            await self.send_and_save_data(active_matches)

        except Exception as e:
            await self.send_to_logs(f"Произошла ошибка: {str(e)}")

    async def close(self):
        if self.driver:
            self.driver.quit()
            await self.send_to_logs("Драйвер был закрыт принудительно")

    def __del__(self):
        if self.driver:
            self.driver.quit()
            print("Драйвер закрыт")

    async def run(
            self,
            *args,
            **kwargs
            ):
        """
        Основной метод для запуска парсера.
        """
        try:
            await self.init_async_components()
            leagues = kwargs.get('leagues', LEAGUES)
            await self.get_url()
            await self.main_page()
            while True:
                await self.collect_odds_data(leagues)
                await asyncio.sleep(1)  # Пауза между циклами сбора данных
        except Exception as e:
            await self.send_to_logs(f"Произошла ошибка: {str(e)}")
        finally:
            self.driver.quit()


if __name__ == "__main__":
    LOCAL_DEBUG = 1
    HEADLESS = False
    fetcher = OddsFetcher()
    asyncio.run(fetcher.run())