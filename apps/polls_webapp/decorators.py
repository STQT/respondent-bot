from functools import wraps
from typing import Callable

from django.http import HttpRequest
from django.shortcuts import redirect


def require_tg_user(view_func: Callable):
    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if request.session.get("tg_user_id"):
            return view_func(request, *args, **kwargs)
        return redirect("polls_webapp:login")

    return _wrapped

