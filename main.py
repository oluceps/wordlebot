import asyncio
import json
import logging
import random
import io
from asyncio import TaskGroup
from contextlib import asynccontextmanager

from PIL import Image
import numpy as np
from pyrogram import Client, filters, idle
from pyrogram.types import Message

logging.basicConfig(format='%(asctime)s [%(levelname).1s] [%(name)s] %(message)s', level=logging.INFO)
logging.getLogger('pyrogram').setLevel(logging.WARNING)


def get_words(file_name):
    with open(f'dicts/{file_name}.txt') as f:
        _words = f.read()
        return [_words[i:i + 5] for i in range(0, len(_words), 5)]


@asynccontextmanager
async def app_group(apps: list[Client]):
    async with TaskGroup() as group:
        for _app in apps:
            group.create_task(_app.__aenter__())
    try:
        yield apps
    finally:
        async with TaskGroup() as group:
            for _app in apps:
                group.create_task(_app.__aexit__())


class Wordle:
    guess_list = get_words('coca_derivative_2000')
    valid_set = set(get_words('all_valid'))

    def __init__(self):
        self.word = random.choice(self.guess_list)
        self._current_pic = None
        self.won = False

    def guess(self, g):
        g = g.lower()
        if g == self.word:
            self.won = True
        else:
            if g not in self.valid_set:
                return False
        row = np.hstack([letters[ord(gi) - 97][(gi in self.word) + (gi == wi)] for gi, wi in zip(g, self.word)])
        self._current_pic = row if self._current_pic is None else np.vstack([self._current_pic, row])
        return True

    @property
    def current_pic(self):
        pic = self._current_pic
        if pic is not None:
            if pic.shape[0] < 2 * SIZE:
                pic = np.vstack([pic, empty])
            return Image.fromarray(pic)


SIZE = 204
FLAME_DANCE_ID = 'CAACAgIAAxkBAANTZv8keJ35IpRtw4I8I3FkhgABwKi6AAJeEgAC7JkpSXzv2aVH92Q7HgQ'
DISABLED = object()
letters = np.array(Image.open('letters.png'))
empty = np.hstack([letters[:SIZE, -SIZE:]] * 5)
letters = [[letters[i:i + SIZE, j:j + SIZE] for j in range(0, SIZE * 3, SIZE)] for i in range(0, SIZE * 26, SIZE)]

with open('config.json') as f:
    config = json.load(f)

game_state: dict[int, Wordle] = {}
bot_config = config['bot']
bot = Client(config['bot']['name'], config['api_id'], config['api_hash'], bot_token=config['bot']['token'])
user = Client(config['user']['name'], config['api_id'], config['api_hash'], phone_number=config['user']['phone_number'])


@filters.create
def enabled_filter(_, __, m):
    return game_state.get(m.chat.id) is not DISABLED


@filters.create
def word_filter(_, __, m):
    return len(m.text) == 5 and m.text[0] != '/'


word_filter = filters.text & word_filter
enabled_filter |= filters.private  # private always enabled


@bot.on_message(filters.command('new') & enabled_filter)
async def new_game(_, message: Message):
    game_state[message.chat.id] = Wordle()
    await message.reply('Created and joined Wordle.', quote=True)


@bot.on_message(word_filter & enabled_filter)
async def guess(_, message: Message):
    if message.chat.id not in game_state:
        return
    game = game_state[message.chat.id]

    image = io.BytesIO()
    already_won = game.won
    success = False
    if already_won:
        await message.reply('Already solved. You can play /new Wordle or /share tiles with friends.')
    else:
        valid = game.guess(message.text)
        if not valid:
            await message.reply('Not a valid english word!')
            return
        success = game.won
    game.current_pic.save(image, format='PNG')
    image.name = "wordle.png"
    await message.reply_photo(image, quote=False)
    if success and not already_won:
        await message.reply("Congrats on xxxth wordle! /share or /new")
        await message.reply_sticker(FLAME_DANCE_ID, quote=False)


@bot.on_message(filters.command('enable') & filters.group)
async def enable(_, message):
    await message.reply("Wordlebot remastered is enabled for this group.")
    game_state[message.chat.id] = None


@bot.on_message(filters.command('disable') & filters.group)
async def disable(_, message):
    game_state[message.chat.id] = DISABLED
    await message.reply("Wordlebot remastered is disabled for this group.")


@user.on_message(filters.user('hiwordlebot') & filters.group)
async def auto_disable(_, message):
    if game_state[message.chat.id] is not DISABLED:
        await bot.send_message(message.chat.id, "Wordlebot is detected. Disabling Wordlebot remastered.")
        game_state[message.chat.id] = DISABLED


async def main():
    async with app_group([bot, user]):
        await idle()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    run = loop.run_until_complete(main())
