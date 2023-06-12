# this bot is inteded to transcribe all voice and video messages sent by user, using telethon
import os

import yaml
from telethon import TelegramClient, events, sync
from whisper import transcribe

# import from config/config.yml
with open('../config/config.yml', 'r') as config_file:
    config_data = yaml.safe_load(config_file)

api_key = config_data['api_id']
api_hash = config_data['api_hash']

client = TelegramClient('session_name', api_key, api_hash)

async def transcribe_message(message, prompt=""):
    if message.voice:
        print("voice message")
        # download the voice message
        filename = await client.download_media(message, file="voice.ogg")
        print(f"file downloaded: {filename}")
        if os.path.exists(filename):
            transcription = await transcribe.transcribe(filename, prompt)
            return transcription


# client on, when user sends a message, it will be transcribed
@client.on(events.NewMessage(incoming=False))
async def my_event_handler(event):
    me = await client.get_me()
    from_id = event.message.from_id
    peer_id = event.message.peer_id
    print(event.message.message)
    prepend_message = "<code>Transcribed with Wisper Bot</code> \n\n"

    # if contains @transcribe, then transcribe the message
    # check with regex
    to_transcribe = False


    if "@transcribe" in event.message.message:
        # check if it is reply to a message
        print("transcribe")
        # schema is @transcribe <prompt>
        # get the prompt
        prompt = event.message.message.split("@transcribe")[1]

        if not event.message.reply_to_msg_id:
            print("no reply")
            return
        # get the message to transcribe
        message_to_transcribe = await client.get_messages(peer_id, ids=event.message.reply_to_msg_id)
        transcription = await transcribe_message(message_to_transcribe, prompt)
        if transcription is not None:
            message_to_send = prepend_message + transcription
            response = await client.send_message(peer_id, message_to_send, parse_mode="html")
        return





    # transcription = await transcribe_message(event.message)
    # # check if it was a voice message
    #
    #
    # if transcription is not None:
    #     message_to_send = prepend_message + transcription
    #     response = await client.send_message(peer_id, message_to_send, parse_mode="html")


client.start()
client.run_until_disconnected()
