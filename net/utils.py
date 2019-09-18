# -*- coding: utf8 -*-
u"""杂项."""

from functools import wraps
from threading import Thread

def async_call(f):
    u"""子线程执行."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        thr = Thread(target=f, args=args, kwargs=kwargs)
        thr.start()
    return wrapper