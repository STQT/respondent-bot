import requests
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, LabeledPrice, PreCheckoutQuery
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from magic_filter import F

from apps.bot.states import OrderStates
from apps.orders.models import Order, OrderProduct
from apps.users.models import TGUser

order_router = Router()


async def get_address_from_geolocation(latitude: float, longitude: float) -> str | None:
    """
    Преобразовать геолокацию (широта, долгота) в текстовый адрес с помощью API.
    """
    try:
        # Используем Nominatim (OpenStreetMap) API
        url = f"https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": latitude,
            "lon": longitude,
            "format": "json",
            "addressdetails": 1,
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Проверяем, если адрес найден
        address = data.get("display_name")
        return address
    except Exception as e:
        print(f"Ошибка при получении адреса по геолокации: {e}")
        return None


async def get_order_data(state: FSMContext):
    """Получить сведения о заказе из состояния."""
    data = await state.get_data()
    return {
        "order_items": data.get("order_items", []),
        "total_sum": data.get("total_sum", 0),
        "order_id": data.get("order_id"),
        "customer_address": data.get("customer_address"),
    }


async def create_order(user: TGUser, payment_type: str, total_sum: float, address: str = None):
    """Создание заказа в базе данных."""
    return await Order.objects.acreate(
        customer_name=user.fullname,
        customer_phone=user.phone,
        customer_address=address,
        cash_type=payment_type,
        total_sum=total_sum,
    )


async def save_order_items(order, order_items, lang: str):
    """Сохранение позиций заказа в базе данных."""
    for item in order_items:
        product_name = getattr(item["product"], f"name_{lang}")
        await OrderProduct.objects.acreate(
            order=order,
            product_name=product_name,
            product_count=item["count"],
            total_price=item["price"],
        )


@order_router.message(
    OrderStates.payment_type,
    F.text.in_([str(_("Naqd")), str(_("ClickUZ")), str(_("Yetkazib berish"))]),
)
async def handle_payment_type(message: types.Message, state: FSMContext, user: TGUser | None):
    order_data = await get_order_data(state)
    payment_type = message.text
    order_items = order_data["order_items"]
    total_sum = order_data["total_sum"]

    if payment_type == str(_("Naqd")):
        order = await create_order(user, payment_type, total_sum)
        await save_order_items(order, order_items, user.lang)
        await finalize_order(order_data, message, user)

    elif payment_type == str(_("ClickUZ")):

        # Генерация счёта на основе данных заказа
        title = str(_("Sizning buyurtmangiz"))
        description = str(_("Quyidagi mahsulotlar uchun to'lov:"))
        prices = [
            LabeledPrice(
                label=str(_(
                    "{product} ({count} dona)"
                )).format(
                    product=getattr(item['product'], f'name_{user.lang}'),
                    count=item['count']
                ),
                amount=item["price"] * 100,
            )
            for item in order_items
        ]

        await message.bot.send_invoice(
            chat_id=message.chat.id,
            title=title,
            description=description,
            payload="order_payment",
            provider_token=settings.PAYMENT_PROVIDER_TOKEN,
            currency="UZS",
            prices=prices,
            start_parameter="purchase",
        )

    elif payment_type == str(_("Yetkazib berish")):
        # Запрос геолокации или текстового адреса с кнопкой "Отправить адрес"
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=str(_("📍 Manzilni yuborish")), request_location=True)],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await message.answer(str(_("Iltimos, manzilingizni yuboring 📍 yoki manzilni yozing ✏️")),
                             reply_markup=keyboard)
        await state.set_state(OrderStates.delivery_address)


@order_router.message(OrderStates.delivery_address, F.location)
async def handle_delivery_address(message: types.Message, state: FSMContext, user: TGUser | None):
    location = message.location
    order_data = await get_order_data(state)
    address = await get_address_from_geolocation(latitude=location.latitude, longitude=location.longitude)
    order_data['address'] = address  # noqa
    # Создаем заказ с геолокацией
    order = await create_order(
        user,
        str(_("Yetkazib berish")),
        order_data["total_sum"],
        address=address,  # Сохраняем координаты в customer_address
    )
    await save_order_items(order, order_data["order_items"], user.lang)

    await message.answer(
        str(_("Buyurtmangiz yetkazilmoqda. Tez orada sizga yetib boradi.")),
        reply_markup=types.ReplyKeyboardRemove()
    )
    await finalize_order(order_data, message, user)
    await state.clear()


@order_router.message(OrderStates.delivery_address, F.text)
async def handle_text_address(message: types.Message, state: FSMContext, user: TGUser | None):
    address = message.text
    order_data = await get_order_data(state)
    order_data['address'] = address  # noqa

    # Создаем заказ с текстовым адресом
    order = await create_order(
        user,
        str(_("Yetkazib berish")),
        order_data["total_sum"],
        address=address,
    )
    await save_order_items(order, order_data["order_items"], user.lang)

    await message.answer(
        str(_("Buyurtmangiz yetkazilmoqda. Tez orada sizga yetib boradi.")),
        reply_markup=types.ReplyKeyboardRemove()
    )
    await finalize_order(order_data, message, user)
    await state.clear()


@order_router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@order_router.message(F.content_type.in_({types.ContentType.SUCCESSFUL_PAYMENT}))
async def successful_payment_handler(message: types.Message, state: FSMContext, user: TGUser | None):
    payment_info = message.successful_payment
    order_data = await get_order_data(state)

    # Создание заказа только после успешной оплаты
    order = await create_order(
        user, str(_("ClickUZ")), order_data["total_sum"], address=order_data.get("customer_address")
    )
    await save_order_items(order, order_data["order_items"], user.lang)

    await message.answer(
        str(_("To'lov amalga oshdi!\n\n"
              "Buyurtma: #{order_id}\n"
              "Summa: {summa} {currency}"
              )
            ).format(summa=payment_info.total_amount / 100,
                     currency=payment_info.currency,
                     order_id=order.id)
    )
    await state.clear()
    await finalize_order(order_data, message, user)


async def finalize_order(order_data, message: types.Message, user: TGUser):
    order_items = order_data["order_items"]
    total_sum = order_data["total_sum"]
    """Завершение оформления заказа."""
    order_summary = "\n".join(
        [
            str(_(
                "{product} ({count} dona) - {price} UZS"
            )).format(
                product=getattr(item['product'], f'name_{user.lang}'),
                count=item['count'],
                price=item['price']
            )
            for item in order_items
        ]
    )
    await message.answer(
        str(_(
            "Buyurtmangiz qabul qilindi!\n\n"
            "Mahsulotlar:\n{order_summary}\n\n"
            "Umumiy summa: {total_sum} UZS\n\n"
            "Tez orada operator siz bilan bog'lanadi."
        )).format(order_summary=order_summary, total_sum=total_sum),
        reply_markup=types.ReplyKeyboardRemove(),
    )

    operator_message = f"Yangi buyurtma:\n\n" \
                       f"Foydalanuvchi: {user.fullname}\n" \
                       f"Telefon raqam: {user.phone}\n\n" \
                       f"Mahsulotlar:\n{order_summary}\n\n" \
                       f"Umumiy summa: {total_sum} UZS\n\n"
    if order_data.get("address"):
        operator_message += f"Manzil: {order_data['address']}"
    # Отправляем сообщение в чат оператора
    await message.bot.send_message(
        settings.OPERATOR_CHAT_ID,
        operator_message,
        parse_mode="Markdown",
    )
