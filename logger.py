import logging
import datetime as dt

logging.basicConfig(
    filename="logs/logs.txt",
    level=logging.DEBUG,  # 出力するログレベルの閾値を設定
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger()

logger.debug("DEBUGログです。")
logger.info("INFOログです。")
logger.warning("WARNINGログです。")
logger.error("ERRORログです。")
logger.critical("CRITICALログです。")

for i in range(10):
    try:
        1 / 0
    except ZeroDivisionError as e:
        logger.exception("割り算が正しくありません。")

    try:
        dt.datetime.strptime("123", "%y-%m-%d %H:%M:%S")
    except ValueError as e:
        logger.exception("日時形式が正しくありません。")
