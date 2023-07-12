# this bot is inteded to transcribe all voice and video messages sent by user, using telethon
import io
import os
from datetime import datetime, timedelta

import openai
import yaml
from telethon import TelegramClient, events, sync
from whisper import transcribe
import uuid

# import from config/config.yml
with open('../config/config.yml', 'r') as config_file:
    config_data = yaml.safe_load(config_file)

api_key = config_data['api_id']
api_hash = config_data['api_hash']

client = TelegramClient('ruby.session', api_key, api_hash)

from statemachine import StateMachine, State


# Define our states
class Job():
    def __init__(self, message, output_format):
        super().__init__()
        self.id = str(uuid.uuid4())
        self.output_format = output_format
        self.message = message
        self.job_directory = self.create_job_directory()
        self.prompt = ""
        self.is_large = None
        self.fragments = None
        self.converted_media_path = None
        self.result = None

    def create_job_directory(self):
        job_directory = "jobs/" + self.id
        if not os.path.exists(job_directory):
            os.makedirs(job_directory)

        return job_directory

    async def download(self):
        def callback(current, total):
            print('Downloaded', current, 'out of', total,
                  'bytes: {:.2%}'.format(current / total))

        if self.message.voice:
            filename = self.id + ".ogg"
            print(f"Handling voice message: {filename}")
            filename = await client.download_media(self.message, file=self.job_directory + "/" + filename,
                                                   progress_callback=callback)
            print(f"Downloaded voice message to {filename}")

    async def convert(self):
        self.converted_media_path = await transcribe.convert_media_to_mp3(self.job_directory + "/" + self.id + ".ogg")
        return

    async def check_size(self):
        self.is_large = transcribe.is_large(self.converted_media_path)
        return

    async def process_audio(self):
        print(f"Processing audio for job {self.id}")
        self.result = await transcribe.process_job(job_id=self.id)
        # if self.is_large:
        #     self.result = await transcribe.process_audio(self.fragments, self.job_directory)
        # else:
        #     with open(self.converted_media_path, "rb") as file:
        #         self.result = await openai.Audio.atranscribe("whisper-1", file, prompt=self.prompt,
        #                                                      response_format=self.output_format)
        return

    def get_result(self):
        print(f"Processing result for job {self.id}")
        # need to parse the result as a single message
        result = ""
        for chunk in self.result["segments"]:
            print(chunk)
            result += chunk["text"]

        return result




async def transcribe_message(message, prompt="", format=""):
    job_id = str(uuid.uuid4())
    job_directory = "jobs/" + job_id
    # create directory in jobs/job_id
    if not os.path.exists(job_directory):
        os.makedirs(job_directory)

    def progress_callback(current, total):
        print('Downloaded', current, 'out of', total,
              'bytes: {:.2%}'.format(current / total))

    filename = ""
    if message.voice:
        filename = job_id + ".ogg"
        print(f"Handling voice message: {filename}")

        filename = await client.download_media(message, file=job_directory + "/" + filename, progress_callback=progress_callback)
        print(f"Downloaded voice message to {filename}")

    elif message.file:
        filename = job_id + message.file.ext
        print(f"Handling file message: {filename}")

        filename = await client.download_media(message, file=job_directory + "/" + filename, progress_callback=progress_callback)
        print(f"Downloaded file message to {filename}")

    if os.path.exists(filename):
        transcription = await transcribe.process_audio(filename, prompt=prompt, response_format=format)
        return transcription

from datetime import timedelta

def seconds_to_mmss(sec):
    td = timedelta(seconds=int(float(sec)))
    return str(td).zfill(5)
def make_outline(input_dict):
    # make input a string from
    string_input = ""
    for segment in input_dict.get("segments"):
        string_input += f"{seconds_to_mmss(segment.get('start'))} - {segment.get('text')} \n"
    outline = openai.ChatCompletion.create(
        model="gpt-4",
        temperature=0,
        messages=[{"role": "system", "content": """You are an AI tasked with creating timestamps and summaries for YouTube videos based on user's audio messages. Your task is to produce a succinct summary of the message and designate specific chapters with timestamps.

Rules to Follow:
1. Timestamps should be in the format of minutes:seconds (mm:ss). Do not include milliseconds!
2. Be succinct in your summaries and chapter titles. Avoid including excessive details.
3. There MUST be a time gap of 20-40 seconds between each timestamp. This is crucial.
4. Make as least chapters as possible. The ideal number of chapters is 3-5 for small video.

Example Output:
```
Language: English
*I should answer in English*

**Summary**
Mom describes her busy day, including a visit to the post office and a city council meeting, then coffee with Mrs. Johnson. She asks about your day at school, particularly your math test and history project. Then, she lists the items she needs from the grocery store: milk, whole grain bread, eggs, fruits (apples, bananas, and peaches), dog food for Max, and laundry supplies.

**Outline**
00:00 - Mom's Day: Post Office and City Council
02:00 - Coffee with Mrs. Johnson
03:20 - Inquiry about Your School Day
04:40 - Grocery Item 1: Milk
05:10 - Grocery Item 2: Whole Grain Bread
05:40 - Grocery Item 3: Eggs
06:10 - Grocery Item 4: Fruits (Apples, Bananas, and if possible, Peaches)
07:10 - Grocery Item 5: Dog Food for Max
07:40 - Grocery Item 6: Laundry Detergent and Fabric Softener
```
Example 2:
```
Language: English
*I should answer in English*

**Summary**
The user discusses feeling secure in different environments, contrasting life in a big, developed city with a less developed one, and emphasizing the varying levels of safety for women at night. The user further compares experiences between Ukraine and Europe, asserting they felt safer in Ukraine despite appearances, while in Europe, they witnessed numerous unsettling situations due to immigrant attention.

**Outline**
00:00 - Conclusion on Generally Feeling Safe
00:34 - City Life: Sense of Security
00:56 - Life in Less Developed Areas
01:44 - Women's Night Time Safety
02:10 - Comparison: Feeling Safer in Ukraine
02:58 - Few Negative Situations in Ukraine
03:52 - Numerous Unsettling Situations in Europe
```
"""},
            {"role": "user", "content": f"{string_input}"}]
    )
    # make openai prompt

    return outline.choices[0].message.content

# client on, when user sends a message, it will be transcribed
@client.on(events.NewMessage(incoming=False))
async def my_event_handler(event):
    me = await client.get_me()
    from_id = event.message.from_id
    peer_id = event.message.peer_id
    print(event.message.message)
    prepend_message = "```Transcribed with Wisper Bot``` \n\n"

    # if contains @transcribe, then transcribe the message
    # check with regex
    to_transcribe = False

    message_to_transcribe = await client.get_messages(peer_id, ids=event.message.reply_to_msg_id)

    async def check_reply():
        if not event.message.reply_to_msg_id:
            await client.send_message(peer_id, "Please reply to a message to transcribe")
            return

    if "@transcribe_vtt_file" in event.message.message:
        await check_reply()
        # schema is @transcribe_vtt_file <prompt>
        prompt = event.message.message.split("@transcribe_vtt_file")[1]
        format = "vtt"

    elif "@transcribe" in event.message.message:
        await check_reply()
        prompt = event.message.message.split("@transcribe")[1]
        format = "text"

    else:
        return

    job = Job(message_to_transcribe, "text")
    await job.download()
    await job.convert()
    await job.check_size()
    await job.process_audio()

    if job.result:
        if "@outline" in event.message.message:
            outline = make_outline(job.result)
            # await client.send_message(peer_id, prepend_message + outline, parse_mode="html")
            # answer to message_to_transcribe
            await client.send_message(peer_id, prepend_message + outline, parse_mode="markdown", reply_to=message_to_transcribe)
        else:
            await client.send_message(peer_id, prepend_message + job.get_result(), parse_mode="markdown", reply_to=message_to_transcribe)



    # get the message to transcribe

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
