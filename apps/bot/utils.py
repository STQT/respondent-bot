from django.core.cache import cache
from django.db import IntegrityError

from apps.users.models import TGUser


async def async_get_or_create_user(defaults=None, **kwargs):
    """
    Async equivalent of Django's get_or_create.
    """
    defaults = defaults or {}
    try:
        # Try to get the object
        obj = await TGUser.objects.aget(**kwargs)
        created = False
    except TGUser.DoesNotExist:
        # Object does not exist, attempt to create it
        try:
            obj = await TGUser.objects.acreate(**{**kwargs, **defaults})
            created = True
        except IntegrityError:
            # Handle a race condition where the object was created between `aget` and `acreate`
            obj = await TGUser.objects.aget(**kwargs)
            created = False
    return obj, created


def get_user_shopping_cart(user_id):
    key = f"shopping_cart:{user_id}"
    # Получаем корзину из кэша
    cart_items = cache.get(key)

    # Если корзина не найдена, можно вернуться пустому словарю
    if not cart_items:
        return {}

    # Преобразуем из байтов в строки
    decoded_cart_items = {key.decode('utf-8'): value.decode('utf-8') for key, value in cart_items.items()}
    return decoded_cart_items


def get_cart_items_list(cart_items):
    items = []
    for item_key, price in cart_items.items():
        item_name, count = item_key.split(":")
        items.append({'name': item_name, 'count': count})
    return items


def get_cart_items_text(cart_items):
    cart_items_text = ""
    total_price = 0
    for item_key, price in cart_items.items():
        item_name, count = item_key.split(":")
        item_price = int(price)
        item_total_price = item_price * int(count)
        total_price += item_total_price
        cart_items_text += f"{count} ✖️ {item_name} {item_price} so'm\n"

    return cart_items_text, total_price


def clear_user_shopping_cart(user_id):
    key = f"shopping_cart:{user_id}"
    # Удаляем корзину из кэша
    cache.delete(key)
