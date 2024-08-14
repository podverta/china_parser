import json
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSLATE_CASH_PATH = os.path.join(BASE_DIR, 'translate_cash.json')

def load_translate_cash() -> dict:

    if os.path.exists(TRANSLATE_CASH_PATH):
        with open(TRANSLATE_CASH_PATH, 'r', encoding='utf-8') as file:
            return json.load(file)
    return {}


def save_translate_cash(translate_cash) -> None:
    with open(TRANSLATE_CASH_PATH, 'w', encoding='utf-8') as file:
        json.dump(translate_cash, file, ensure_ascii=False, indent=4)

