# this bot is inteded to transcribe all voice and video messages sent by user, using telethon
import os

import yaml
from telethon import TelegramClient, events, sync

# import from config/config.yml


def fetch_user_ids(session_name, group_id):
    # import from config/config.yml

    api_key = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")

    client = TelegramClient(session_name, api_key, api_hash)
    user_ids = []
    try:
        with client:
            client.start()
            # my client should see the group at least once
            user_ids = client.loop.run_until_complete(fetch_participants_id(client, group_id))
            # list users in the group
    finally:
        client.disconnect()

    return user_ids


async def fetch_participants_id(client, group_id):
    dialogs = await client.get_dialogs()

    # get users from the group
    group = await client.get_entity(group_id)
    participants = await client.get_participants(group)

    user_ids = []
    for user in participants:
        user_id = user.id
        user_ids.append(user_id)

    return user_ids
