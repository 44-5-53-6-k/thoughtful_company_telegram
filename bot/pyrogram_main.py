import asyncio
from pyrogram import Client, filters

api_id = "20282180"
api_hash = "a1264d4ca1cc770ed1ed1bee674ab46a"

pyroApp = Client("my_account", api_id=api_id, api_hash=api_hash, bot_token="5899466534:AAF3LVMo2a5ybcjVv5TMo2Je0BSl2smyKX8")

# @pyroApp.on_message(filters.text & filters.private)
# async def echo(client, message):
#     await message.reply(message.text)



