from pydantic import BaseModel


class ParserRequest(BaseModel):
    """
    Валидация данных для проверки
    """
    parser_name: str
    args: list = []
    kwargs: dict = {}