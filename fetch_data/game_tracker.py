import asyncio
from typing import Dict, Any

class GameTracker:
    def __init__(self, previous_data: Dict[str, Any]):
        """
        Инициализация трекера игр.

        :param previous_data: Словарь с предыдущими данными игр.
        """
        self.previous_data = previous_data

    async def check_games_status(self, current_data: Dict[str, Any]):
        """
        Асинхронно проверяет статус игр, добавляя метку завершения, если игра пропала из текущих данных.

        :param current_data: Словарь с актуальными данными о лигах и играх.
        """
        tasks = []
        for site, leagues in self.previous_data.items():
            for league, games in leagues.items():
                for game in games:
                    tasks.append(self._check_game_finished(site, league, game,
                                                           current_data))

        finished_games = await asyncio.gather(*tasks)
        for game, finished in zip(sum(sum(self.previous_data.values(), []), []),
                                  finished_games):
            if finished:
                game['finished'] = True

    async def _check_game_finished(self, site: str, league: str,
                                   game: Dict[str, Any],
                                   current_data: Dict[str, Any]) -> bool:
        """
        Асинхронно проверяет, завершилась ли игра.

        :param site: Название сайта, откуда получены данные.
        :param league: Название лиги.
        :param game: Данные о конкретной игре.
        :param current_data: Актуальные данные о лигах и играх.
        :return: True, если игра завершена, иначе False.
        """
        for _ in range(200):  # Проверяем в течение 200 секунд
            await asyncio.sleep(1)  # Задержка 1 секунда между проверками
            current_league_data = current_data.get(site, {}).get(league, [])
            if game not in current_league_data:
                return True
        return False