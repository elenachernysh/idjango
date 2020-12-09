from datetime import datetime


def format_date(raw_date: float) -> str:
    format_date = '%B %d, %Y'
    date_from_seconds = datetime.fromtimestamp(raw_date)
    result_date = date_from_seconds.strftime(format_date)
    return result_date


def reduce_info(needed_keys: tuple, data_to_reduce: list) -> list:
    result = [{key: info.get(key, '') for key in needed_keys} for info in data_to_reduce]
    return result


def get_schema(is_secure: bool) -> str:
    return 'https://' if is_secure else 'http://'
