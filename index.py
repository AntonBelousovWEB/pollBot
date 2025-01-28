import asyncio
import csv
import json
import random
from typing import Dict, List
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import Message, Poll, PollAnswer

TOKEN = "bot token" 
CHAT_ID = "-id"
RESULTS_FILE = "quiz_results.csv"
WINS_FILE = "wins.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()

wins: Dict[str, int] = {}
quiz_creation_state = {}

async def load_wins():
    try:
        with open(WINS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

async def save_wins():
    with open(WINS_FILE, 'w') as f:
        json.dump(wins, f, indent=4)

def get_user_identifier(user: types.User) -> str:
    return user.username or str(user.id)

results = []

async def update_csv_results(question: str, options: List[str], correct_option: int, voters: Dict[int, List[str]]):
    try:
        with open(RESULTS_FILE, 'r', newline='', encoding="utf-8") as f:
            reader = csv.DictReader(f)
            global results
            results = list(reader)
    except FileNotFoundError:
        results = []

    new_results = []
    for i, option in enumerate(options):
        voters_list = voters.get(i, [])
        new_results.append({
            'Question': question,
            'Option': option,
            'Voters': ', '.join(voters_list),
            'Is_Correct': 'Yes' if i == correct_option else 'No'
        })
        if i == correct_option:
            for user in voters_list:
                wins[user] = wins.get(user, 0) + 1

    results.extend(new_results)

    fieldnames = ['Question', 'Option', 'Voters', 'Is_Correct']
    with open(RESULTS_FILE, 'w', newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    await save_wins()
    return new_results

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Вот доступные команды:\n"
        "/create_quiz - Создать новую викторину\n"
        "/process - Обработать результаты последней викторины\n"
        "/winners - Показать текущий рейтинг победителей\n"
        "/reset - Сбросить все результаты и начать новый этап викторин"
    )

@dp.message(Command("winners"))
async def show_winners(message: Message):
    if not wins:
        await message.answer("Нет данных о викторинах!")
        return

    wins_text = "🏆 Текущий рейтинг победителей:\n" + "\n".join(
        f"@{username}: {score} побед" for username, score in wins.items()
    )
    await message.answer(wins_text)

    max_wins = max(wins.values())
    winners = [user for user, score in wins.items() if score == max_wins]
    winner = random.choice(winners) if len(winners) > 1 else winners[0]
    await message.answer(f"🎉 Победитель: {winner} с {wins[winner]} победами!")

@dp.message(Command("create_quiz"))
async def start_quiz_creation(message: Message):
    quiz_creation_state[message.from_user.id] = {'state': 'waiting_question'}
    await message.answer("Отправьте вопрос для викторины:")

@dp.message(lambda message: message.from_user.id in quiz_creation_state and quiz_creation_state[message.from_user.id]['state'] == 'waiting_question')
async def receive_question(message: Message):
    quiz_creation_state[message.from_user.id].update({
        'question': message.text,
        'state': 'waiting_options',
        'options': []
    })
    await message.answer("Отправляйте варианты ответов по одному. Отправьте /done когда закончите или /cancel если совершили ошибку:")

@dp.message(lambda message: message.from_user.id in quiz_creation_state and quiz_creation_state[message.from_user.id]['state'] == 'waiting_options')
async def receive_option(message: Message):
    if message.text == "/done":
        if len(quiz_creation_state[message.from_user.id]['options']) < 2:
            await message.answer("Необходимо минимум 2 варианта ответа!")
            return
        await message.answer("Укажите номер правильного ответа (начиная с 1):")
        quiz_creation_state[message.from_user.id]['state'] = 'waiting_correct'
    if message.text == "/cancel":
        del quiz_creation_state[message.from_user.id]
        await message.answer("Создание викторины отменено.")
    else:
        quiz_creation_state[message.from_user.id]['options'].append(message.text)
        await message.answer(f"Вариант {len(quiz_creation_state[message.from_user.id]['options'])} добавлен. Продолжайте или отправьте /done или отправьте /cancel если допустили ошибку!")

@dp.message(lambda message: message.from_user.id in quiz_creation_state and quiz_creation_state[message.from_user.id]['state'] == 'waiting_correct')
async def receive_correct_option(message: Message):
    try:
        correct_option = int(message.text) - 1
        if 0 <= correct_option < len(quiz_creation_state[message.from_user.id]['options']):
            state = quiz_creation_state[message.from_user.id]
            poll_msg = await bot.send_poll(
                chat_id=CHAT_ID,
                question=state['question'],
                options=state['options'],
                type="quiz",
                correct_option_id=correct_option,
                is_anonymous=False
            )
            await message.answer(f"Викторина создана и отправлена в канал!\nID: {poll_msg.message_id}")
            del quiz_creation_state[message.from_user.id]
        else:
            await message.answer("Неверный номер! Попробуйте еще раз:")
    except ValueError:
        await message.answer("Пожалуйста, введите число!")

voters_data: Dict[int, Dict[int, List[str]]] = {}
correct_options: Dict[int, int] = {}
questions: Dict[int, str] = {}
options_data: Dict[int, List[str]] = {}

@dp.poll()
async def receive_poll(poll: Poll):
    correct_options[poll.id] = poll.correct_option_id
    questions[poll.id] = poll.question
    options_data[poll.id] = [opt.text for opt in poll.options]
    voters_data[poll.id] = {i: [] for i in range(len(poll.options))}

@dp.poll_answer()
async def receive_poll_answer(poll_answer: PollAnswer):
    user = get_user_identifier(poll_answer.user)
    poll_id = poll_answer.poll_id
    option_id = poll_answer.option_ids[0]
    voters_data[poll_id][option_id].append(user)

@dp.message(Command("process"))
async def process_quiz_results(message: Message):
    poll_id = list(voters_data.keys())[-1] if voters_data else None
    if not poll_id or poll_id not in correct_options:
        await message.answer("Нет данных о викторинах!")
        return

    results = await update_csv_results(
        questions[poll_id],
        options_data[poll_id],
        correct_options[poll_id],
        voters_data[poll_id]
    )

    report = f"📊 Результаты викторины: {questions[poll_id]}\n\n"
    for result in results:
        status = "✅" if result['Is_Correct'] == 'Yes' else "❌"
        voters = result['Voters'] if result['Voters'] else "Нет голосов"
        report += f"{status} {result['Option']}\n👥 Проголосовали: {voters}\n\n"

    await message.answer(report)
    await message.answer("Результаты викторины обработаны и сохранены!")

@dp.message(Command("reset"))
async def reset_quiz_data(message: Message):
    global wins, results
    wins = {}
    results = []
    await save_wins()
    with open(RESULTS_FILE, 'w', newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=['Question', 'Option', 'Voters', 'Is_Correct'])
        writer.writeheader()
    await message.answer("Все результаты сброшены. Начат новый этап викторин!")

async def main():
    global wins
    wins = await load_wins()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())