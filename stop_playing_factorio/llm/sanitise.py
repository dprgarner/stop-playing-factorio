import hashlib
import os
import re
from typing import Iterable, Union


def hash(msg: str):
    return hashlib.sha256(f'{os.getenv("SALT")}{msg}'.encode("utf-8")).hexdigest()[:12]


def get_user_ids_map(msgs: Iterable[str]) -> dict[str, str]:
    user_ids = set()
    for msg in msgs:
        user_ids.update(re.findall(r"<@(\d+)>", msg))
    return {f"<@{id}>": f"<@{hash(id)}>" for id in list(user_ids)}


def sanitise(
    input_: Union[str, dict, tuple], str_map: dict[str, str], reversed=False
) -> str:
    if reversed:
        str_map = {v: k for k, v in str_map.items()}

    if type(input_) == str:
        for key, value in str_map.items():
            input_ = input_.replace(key, value)
        return input_
    if type(input_) == dict:
        sanitised = {}
        for k, v in input_.items():
            sanitised[k] = sanitise(v, str_map)
        return sanitised
    if type(input_) == tuple:
        return tuple(sanitise(x, str_map) for x in input_)
    if type(input_) == list:
        return list(sanitise(x, str_map) for x in input_)
    return input_
