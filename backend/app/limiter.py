"""
Instance slowapi partagée entre main.py et les routers.
Module isolé pour éviter les imports circulaires.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
