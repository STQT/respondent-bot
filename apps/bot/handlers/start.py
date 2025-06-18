from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from django.utils.translation import gettext_lazy as _

from apps.bot.states import RegisterForm
from apps.bot.utils import get_current_question
from apps.users.models import TGUser

start_router = Router()

from apps.bot.keyboards.markups import (
    get_gender_keyboard, get_age_keyboard,
    get_education_keyboard, get_location_keyboard,
    GenderChoices, AgeChoices, GraduateChoices, SettlementTypeChoices
)


@start_router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext, user: TGUser | None):
    if user.gender is None:
        await message.answer(
            str(_("1.1. Жинсингизни танланг:")),
            reply_markup=get_gender_keyboard()
        )
        await state.set_state(RegisterForm.get_gender)
    elif user.age is None:
        await message.answer(str(_("1.2. Ёшингизни танланг:")), reply_markup=get_age_keyboard())
        await state.set_state(RegisterForm.get_age)
    elif user.education is None:
        await message.answer(str(_("1.3. Маълумот даражангизни танланг:")), reply_markup=get_education_keyboard())
        await state.set_state(RegisterForm.get_education)
    elif user.location is None:
        await message.answer(str(_("1.4. Сиз қаерда яшайсиз?")), reply_markup=get_location_keyboard())
        await state.set_state(RegisterForm.get_location)
    else:
        await get_current_question(message, state, user)


@start_router.message(RegisterForm.get_gender)
async def gender_chosen(message: Message, state: FSMContext, user: TGUser | None):
    if message.text not in [str(gender.label) for gender in GenderChoices]:
        return await message.answer(str(_("Қуйидаги тугмалардан фойдаланинг 👇")))
    user.gender = message.text
    await user.asave()
    await message.answer(str(_("1.2. Ёшингизни танланг:")), reply_markup=get_age_keyboard())
    await state.set_state(RegisterForm.get_age)


@start_router.message(RegisterForm.get_age)
async def age_chosen(message: Message, state: FSMContext, user: TGUser | None):
    if message.text not in [str(age.label) for age in AgeChoices]:
        return await message.answer(str(_("Қуйидаги ёш диапазонларидан бирини танланг 👇")))
    user.age = message.text
    await user.asave()
    await message.answer(str(_("1.3. Маълумот даражангизни танланг:")), reply_markup=get_education_keyboard())
    await state.set_state(RegisterForm.get_education)


@start_router.message(RegisterForm.get_education)
async def education_chosen(message: Message, state: FSMContext, user: TGUser | None):
    if message.text not in [str(graduate.label) for graduate in GraduateChoices]:
        return await message.answer(str(_("Қуйидаги таълим даражасидан бирини танланг 👇")))
    user.education = message.text
    await user.asave()
    await message.answer(str(_("1.4. Сиз қаерда яшайсиз?")), reply_markup=get_location_keyboard())
    await state.set_state(RegisterForm.get_location)


@start_router.message(RegisterForm.get_location)
async def location_chosen(message: Message, state: FSMContext, user: TGUser | None):
    if message.text not in [str(settlement.label) for settlement in SettlementTypeChoices]:
        return await message.answer(str(_("Қуйидагидан бирини танланг 👇")))
    user.location = message.text
    await user.asave()

    # await message.answer(
    #     str(_("Рўйхатдан ўтиш якунланди ✅\n\n"
    #           "Сиз менюдан фойдаланишингиз мумкин.")),
    #     reply_markup=types.ReplyKeyboardRemove()
    # )
    await state.clear()
    await get_current_question(message, state, user)
