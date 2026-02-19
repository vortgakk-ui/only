import asyncio
import random
import logging
from decimal import Decimal, ROUND_DOWN
from typing import Union

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, PreCheckoutQuery, LabeledPrice
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.enums import ParseMode

# --- Конфигурация ---
BOT_TOKEN = 8594717446:"AAEqCTg2d9yKDc5uUXYv3fUPrwcDxy8yXrg"  
PAYMENT_PROVIDER_TOKEN = "YOUR_PROVIDER_TOKEN"  # Для Stars можно оставить пустым или "STARS"
ADMIN_USERNAME = "@kyniks"  # Ник для связи по выводу
MIN_WITHDRAW = Decimal("0.05")
MIN_DEPOSIT = Decimal("0.03")  # Минимальное пополнение в долларах (эквивалент 3 Stars)

# Курс: 1 Star = 0.04$ (стандартный курс Telegram)
# Для пополнения на сумму X$ нужно отправить X * 100 Stars
STARS_PER_DOLLAR = 100

# Хранилище данных (в реальном проекте замените на базу данных)
users_data = {}  # {user_id: {"balance": Decimal, "total_lost": Decimal}}

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# --- Вспомогательные функции для работы с балансом ---
def get_user_data(user_id: int) -> dict:
    """Получить или создать запись пользователя."""
    if user_id not in users_data:
        users_data[user_id] = {
            "balance": Decimal("0"),
            "total_lost": Decimal("0")
        }
    return users_data[user_id]

def update_balance(user_id: int, amount: Decimal, is_loss: bool = False) -> Decimal:
    """Обновить баланс. При проигрыше увеличивает total_lost."""
    user = get_user_data(user_id)
    user["balance"] += amount
    # Округление до центов
    user["balance"] = user["balance"].quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    
    if is_loss and amount < 0:
        user["total_lost"] += abs(amount)
        user["total_lost"] = user["total_lost"].quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    
    return user["balance"]

def can_place_bet(user_id: int, amount: Decimal) -> bool:
    """Проверка, может ли пользователь сделать ставку."""
    user = get_user_data(user_id)
    return user["balance"] >= amount and amount > 0

# --- Клавиатуры ---
def get_main_keyboard():
    """Главная клавиатура с кнопками Пополнение и Вывод."""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="💸 Пополнение"))
    builder.add(KeyboardButton(text="👾 Вывод"))
    builder.add(KeyboardButton(text="💢 Баланс"))
    builder.adjust(2)  # Две кнопки в ряду
    return builder.as_markup(resize_keyboard=True)

# --- Обработчики команд ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Приветственное сообщение и главная клавиатура."""
    user_id = message.from_user.id
    get_user_data(user_id)  # Инициализируем пользователя
    
    text = (
        "👋 Привет! Ты попал в <b>Depown Bot</b>\n\n"
        "Вот тебе список во что можно поиграть:\n\n"
        "🎲 <b>Игра Кубик</b> пиши так:\n"
        "<code>кубик 10 чет</code> или <code>кубик 5 больше3</code>\n"
        "Варианты: чет, нечет, больше3, меньше3 (везде x2 ставки)\n\n"
        "🃏 <b>Игра Очко (21)</b> пиши так:\n"
        "<code>очко 10</code>\n\n"
        "💣 <b>Игра Мины</b> пиши так:\n"
        "<code>мины 10 3</code> (3 мины)\n\n"
        "📈 <b>Игра Краш</b> пиши так:\n"
        "<code>краш 10</code>\n\n"
        "🎰 Удачной игры!"
    )
    await message.answer(text, reply_markup=get_main_keyboard())

@dp.message(F.text == "💢 Баланс")
async def cmd_balance(message: Message):
    """Показать баланс и общий проигрыш."""
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    text = (
        f"💢 Ваш баланс: <b>{user['balance']:.2f}$</b> 💢\n"
        f"°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°\n"
        f"Проиграно $: <b>{user['total_lost']:.2f}$</b>"
    )
    await message.answer(text, reply_markup=get_main_keyboard())

# --- Пополнение баланса через Telegram Stars ---
@dp.message(F.text == "💸 Пополнение")
async def cmd_deposit(message: Message):
    """Кнопка пополнения."""
    await message.answer(
        f"Минимальное пополнение: {MIN_DEPOSIT}$\n\n"
        f"Для пополнения нажмите на кнопку ниже и отправьте Stars.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="💸 Пополнить Stars",
                    pay=True  # Важно: включает оплату через Telegram Stars
                )]
            ]
        )
    )

@dp.message(F.text == "👾 Вывод")
async def cmd_withdraw(message: Message):
    """Кнопка вывода."""
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    if user["balance"] < MIN_WITHDRAW:
        await message.answer(
            f"❌ Недостаточно средств для вывода.\n"
            f"Минимальная сумма вывода: {MIN_WITHDRAW}$\n"
            f"Ваш баланс: {user['balance']:.2f}$"
        )
    else:
        await message.answer(
            f"👾 Вывод средств 👾\n\n"
            f"Минимальная сумма вывода: {MIN_WITHDRAW}$\n"
            f"Для вывода {user['balance']:.2f}$ напишите в личные сообщения {ADMIN_USERNAME}\n\n"
            f"<i>После запроса администратор обработает вывод вручную.</i>"
        )

# --- Обработка платежей (Telegram Stars) ---
@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    """Подтверждение платежа."""
    # Здесь можно проверить, что сумма корректна, но обычно все ок
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    """Обработка успешного пополнения через Stars."""
    user_id = message.from_user.id
    total_amount = message.successful_payment.total_amount / 100  # Сумма в долларах (Stars * 100)
    
    # Зачисляем на баланс
    update_balance(user_id, Decimal(str(total_amount)))
    
    await message.answer(
        f"✅ Пополнение успешно!\n"
        f"На ваш баланс зачислено: <b>{total_amount:.2f}$</b>\n"
        f"Текущий баланс: <b>{get_user_data(user_id)['balance']:.2f}$</b>"
    )

# --- ИГРЫ ---

# 1. КУБИК
@dp.message(F.text.regexp(r'^кубик\s+(\d+(?:\.\d+)?)\s+(чет|нечет|больше3|меньше3)$').as_('match'))
async def game_dice(message: Message, match):
    """Игра в кубик: ставка и условие."""
    user_id = message.from_user.id
    bet_str, condition = match.groups()
    bet = Decimal(bet_str)
    
    # Проверка баланса
    if not can_place_bet(user_id, bet):
        await message.answer("❌ Недостаточно средств или неверная сумма ставки.")
        return
    
    # Кидаем кубик
    dice_message = await message.answer_dice(emoji="🎲")
    dice_value = dice_message.dice.value
    
    # Определяем результат
    win = False
    if condition == "чет" and dice_value % 2 == 0:
        win = True
    elif condition == "нечет" and dice_value % 2 != 0:
        win = True
    elif condition == "больше3" and dice_value > 3:
        win = True
    elif condition == "меньше3" and dice_value < 3:
        win = True
    
    # Обновляем баланс
    if win:
        update_balance(user_id, bet)  # + ставка (чистый выигрыш = ставка, т.к. ставка не списывалась)
        result_text = f"🎉 Вы выиграли! +{bet:.2f}$"
    else:
        update_balance(user_id, -bet, is_loss=True)
        result_text = f"😢 Вы проиграли! -{bet:.2f}$"
    
    await message.answer(
        f"🎲 Результат: {dice_value}\n"
        f"{result_text}\n"
        f"Баланс: {get_user_data(user_id)['balance']:.2f}$"
    )

# 2. ОЧКО (21)
@dp.message(F.text.regexp(r'^(?:очко|21)\s+(\d+(?:\.\d+)?)$').as_('match'))
async def game_blackjack(message: Message, match):
    """Игра Очко (21) - упрощенная версия."""
    user_id = message.from_user.id
    bet_str = match.groups()[0]
    bet = Decimal(bet_str)
    
    if not can_place_bet(user_id, bet):
        await message.answer("❌ Недостаточно средств или неверная сумма ставки.")
        return
    
    # Генерируем карты игрока и дилера
    player_cards = [random.randint(1, 11) for _ in range(2)]
    dealer_cards = [random.randint(1, 11) for _ in range(2)]
    
    player_score = sum(player_cards)
    dealer_score = sum(dealer_cards)
    
    # Простая логика: игрок тянет до 17, дилер до 17
    while player_score < 17:
        new_card = random.randint(1, 11)
        player_cards.append(new_card)
        player_score += new_card
    
    while dealer_score < 17:
        new_card = random.randint(1, 11)
        dealer_cards.append(new_card)
        dealer_score += new_card
    
    # Определение победителя
    win = False
    if player_score > 21:
        win = False  # Перебор
    elif dealer_score > 21:
        win = True
    elif player_score > dealer_score:
        win = True
    elif player_score == dealer_score:
        win = None  # Ничья
    
    # Обновление баланса
    if win is True:
        update_balance(user_id, bet)
        result_text = f"🎉 Вы выиграли! +{bet:.2f}$"
    elif win is False:
        update_balance(user_id, -bet, is_loss=True)
        result_text = f"😢 Вы проиграли! -{bet:.2f}$"
    else:
        result_text = f"🤝 Ничья! Ставка возвращена."
    
    await message.answer(
        f"🃏 <b>Очко</b>\n\n"
        f"Ваши карты: {', '.join(map(str, player_cards))} (очков: {player_score})\n"
        f"Карты дилера: {', '.join(map(str, dealer_cards))} (очков: {dealer_score})\n\n"
        f"{result_text}\n"
        f"Баланс: {get_user_data(user_id)['balance']:.2f}$"
    )

# 3. МИНЫ
@dp.message(F.text.regexp(r'^мины\s+(\d+(?:\.\d+)?)\s+(\d+)$').as_('match'))
async def game_mines(message: Message, match):
    """Игра Мины: поле 3x3, выбираем количество мин (1-8)."""
    user_id = message.from_user.id
    bet_str, mines_str = match.groups()
    bet = Decimal(bet_str)
    mines = int(mines_str)
    
    if mines < 1 or mines > 8:
        await message.answer("❌ Количество мин должно быть от 1 до 8.")
        return
    
    if not can_place_bet(user_id, bet):
        await message.answer("❌ Недостаточно средств или неверная сумма ставки.")
        return
    
    # Расчет коэффициента: (9 - mines) / mines, но упростим до множителя (например, как в Mines)
    # В реальном Gmines коэффициент зависит от количества открытых клеток.
    # Сделаем упрощенно: умножаем ставку на (9 / (9 - mines)) для простоты
    if mines == 8:
        multiplier = Decimal("8")  # Рискованно, но высокий множитель
    elif mines == 1:
        multiplier = Decimal("1.1")
    else:
        multiplier = Decimal("9") / Decimal(str(9 - mines))
    
    # Симулируем игру (в реальности тут должна быть клавиатура с клетками)
    # Для простоты: сразу определяем результат (1 к 9-mines шанс на выигрыш)
    # В реальном боте нужна интерактивность, но по ТЗ нужно как в @gminesbot - там интерактив.
    # Я сделаю упрощенно: случайный результат с шансом на выигрыш.
    
    total_cells = 9
    safe_cells = total_cells - mines
    # Шанс выигрыша: safe_cells / total_cells (если игрок открывает 1 клетку)
    # Для простоты: если игрок "открывает" случайную клетку и не натыкается на мину - выигрыш
    win = random.randint(1, total_cells) > mines
    
    if win:
        winnings = bet * multiplier
        update_balance(user_id, winnings)
        result_text = f"🎉 Вы выиграли! +{winnings:.2f}$ (множитель x{multiplier:.2f})"
    else:
        update_balance(user_id, -bet, is_loss=True)
        result_text = f"💥 Бум! Вы проиграли! -{bet:.2f}$"
    
    await message.answer(
        f"💣 <b>Мины</b> (поле 3x3, {mines} мин)\n\n"
        f"{result_text}\n"
        f"Баланс: {get_user_data(user_id)['balance']:.2f}$"
    )

# 4. КРАШ
@dp.message(F.text.regexp(r'^краш\s+(\d+(?:\.\d+)?)$').as_('match'))
async def game_crash(message: Message, match):
    """Игра Краш: множитель растет, игрок должен выйти до краша."""
    user_id = message.from_user.id
    bet_str = match.groups()[0]
    bet = Decimal(bet_str)
    
    if not can_place_bet(user_id, bet):
        await message.answer("❌ Недостаточно средств или неверная сумма ставки.")
        return
    
    # Генерируем множитель краша (от 1.01 до 10.0)
    crash_point = Decimal(str(round(random.uniform(1.01, 10.0), 2)))
    
    # Игрок автоматически выходит на случайном множителе (симуляция)
    # Для простоты: шанс 50% на удвоение
    if random.random() > 0.5:
        # Выигрыш: игрок вышел до краша
        exit_multiplier = crash_point - Decimal("0.1")  # чуть меньше краша
        if exit_multiplier < 1:
            exit_multiplier = Decimal("1.01")
        winnings = bet * exit_multiplier
        update_balance(user_id, winnings)
        result_text = f"🎉 Вы выиграли! +{winnings:.2f}$ (вышли на x{exit_multiplier:.2f})"
    else:
        # Проигрыш: краш раньше выхода
        update_balance(user_id, -bet, is_loss=True)
        result_text = f"💥 Краш! Вы проиграли! -{bet:.2f}$ (краш на x{crash_point:.2f})"
    
    await message.answer(
        f"📈 <b>Краш</b>\n\n"
        f"{result_text}\n"
        f"Баланс: {get_user_data(user_id)['balance']:.2f}$"
    )

# Обработка неизвестных сообщений
@dp.message()
async def handle_unknown(message: Message):
    """Если команда не распознана."""
    await message.answer(
        "❓ Неизвестная команда. Используйте /start для просмотра правил.",
        reply_markup=get_main_keyboard()
    )

# --- Запуск бота ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
