import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(
        name: str,
        log_file: str,
        level=logging.DEBUG,
        max_bytes=10*1024*1024,
        backup_count=2
) -> logging.Logger:
    """
    Настраивает логгер с заданным именем и уровнем логирования.

    :param name: Имя логгера.
    :param log_file: Путь к лог-файлу.
    :param level: Уровень логирования.
    :param max_bytes: Максимальный размер лог-файла в байтах до ротации.
    :param backup_count: Количество резервных копий лог-файлов.
    :return: Настроенный логгер.
    """
    # Получение абсолютного пути к корневой директории проекта
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(project_dir, 'logs')

    # Создание директории логов, если она не существует
    os.makedirs(log_dir, exist_ok=True)

    handler = RotatingFileHandler(
        os.path.join(log_dir, log_file),
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger