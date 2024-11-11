# logger_config.py

import logging
import colorlog

# Уровень SUCCESS, между INFO и WARNING
SUCCESS_LEVEL_NUM = 25
logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")

# Метод для уровня SUCCESS
def success(self, message, *args, **kws):
    if self.isEnabledFor(SUCCESS_LEVEL_NUM):
        self._log(SUCCESS_LEVEL_NUM, message, args, **kws)

# Добавляем метод success в класс Logger
logging.Logger.success = success

# Формат логирования
log_format = (
    "%(log_color)s%(asctime)s | %(levelname)-8s | "
    "%(name)s:%(module)s:%(lineno)d - %(message)s"
)

# Настройка цветного форматирования
color_formatter = colorlog.ColoredFormatter(
    log_format,
    datefmt="%Y-%m-%d %H:%M:%S",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "SUCCESS": "bold_green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    },
)

# Настройка основного логгера
handler = logging.StreamHandler()
handler.setFormatter(color_formatter)

logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)  # Установите уровень логирования
