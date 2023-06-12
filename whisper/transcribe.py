import openai

# get openai key from yml env
import yaml
import os
import ffmpeg
import uuid
import wave

with open('../config/config.yml', 'r') as config_file:
    config_data = yaml.safe_load(config_file)

os.environ["OPENAI_API_KEY"] = config_data['openai_api_key']
openai.api_key = os.getenv("OPENAI_API_KEY")

async def transcribe(filepath, prompt=""):
    # use openai for transcription
    file_type = filepath.split(".")[-1]
    filename = filepath.split(".")[0]
    # generate unique filename
    new_filename = str(uuid.uuid4())

    if file_type == "ogg":
        # convert to wav
        stream = ffmpeg.input(filepath)
        stream = ffmpeg.output(stream, new_filename + ".wav")
        ffmpeg.run(stream)

        # with open(new_filename + ".wav") as file_content:
        #     print(file_content)
        #     result = await openai.Audio.transcribe("whisper-1", file_content)
        #     return result
        file = open(new_filename + ".wav", 'rb')
        print(f"prompt is {prompt}")
        transcript = openai.Audio.transcribe("whisper-1", file, prompt=prompt)
        return transcript.text




    else:
        print("file type not supported")
        return None



