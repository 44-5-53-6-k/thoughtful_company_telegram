import asyncio

from pyrogram import Client


file_id = "BQACAgIAAxkBAAICzmRwtxNiNdxxIB_Aef4AAaPDu-Ng3QACZjMAAkdsiUugRF1yBSbHyS8E"

async def download_file(file_id):
    app = Client("my_account")
    async with app:
        file = await app.download_media(file_id)



asyncio.run(download_file(file_id))
