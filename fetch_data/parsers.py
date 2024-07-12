from fetch_data.akty import FetchAkty
from fetch_data.fb import OddsFetcher

# Здесь указываем список парсеров, который запускается через Celery
parsers = {
    'FetchAkty': FetchAkty,
    'FB': OddsFetcher
}