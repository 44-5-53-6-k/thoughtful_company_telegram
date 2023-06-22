# this bot is inteded to transcribe all voice and video messages sent by user, using telethon
import io
import os
from datetime import datetime, timedelta

import yaml
from telethon import TelegramClient, events, sync
from whisper import transcribe
import uuid

# import from config/config.yml
with open('../config/config.yml', 'r') as config_file:
    config_data = yaml.safe_load(config_file)

api_key = config_data['api_id']
api_hash = config_data['api_hash']

client = TelegramClient('session_name', api_key, api_hash)

async def transcribe_message(message, prompt=""):
    def callback(current, total):
        print('Downloaded', current, 'out of', total,
              'bytes: {:.2%}'.format(current / total))

    job_id = str(uuid.uuid4())
    job_directory = "jobs/" + job_id
    # create directory in jobs/job_id
    if not os.path.exists(job_directory):
        os.makedirs(job_directory)

    if message.voice:
        filename = job_id + ".ogg"
        print(f"Handling voice message: {filename}")

        filename = await client.download_media(message, file=job_directory + "/" + filename, progress_callback=callback)
        print(f"Downloaded voice message to {filename}")
        if os.path.exists(filename):
            transcription = await transcribe.process_audio(filename)
            return transcription

    elif message.file:
        filename = job_id + message.file.ext
        print(f"Handling file message: {filename}")
        filename = await client.download_media(message, file=job_directory + "/" + filename, progress_callback=callback)
        print(f"Downloaded file message to {filename}")
        if os.path.exists(filename):
            transcription = await transcribe.process_audio(filename)
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


    if "@transcribe_vtt_file" in event.message.message:
        if not event.message.reply_to_msg_id:
            await client.send_message(peer_id, "Please reply to a message to transcribe")
            return

        # schema is @transcribe_vtt_file <prompt>
        prompt = event.message.message.split("@transcribe_vtt_file")[1]

        # get the message to transcribe
        message_to_transcribe = await client.get_messages(peer_id, ids=event.message.reply_to_msg_id)
        bytes = await transcribe_message(message_to_transcribe)

        if bytes is not None:
            file = io.BytesIO(bytes)
            file.name = "transcription.txt"
            await client.send_file(peer_id, file, force_document=True)



        return





    # transcription = await transcribe_message(event.message)
    # # check if it was a voice message
    #
    #
    # if transcription is not None:
    #     message_to_send = prepend_message + transcription
    #     response = await client.send_message(peer_id, message_to_send, parse_mode="html")


client.start()
print("bot started")
client.run_until_disconnected()
