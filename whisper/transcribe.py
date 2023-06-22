import shutil

import openai

# get openai key from yml env
import yaml
import os
import ffmpeg
import uuid
import wave

import re
import math
import requests
from pydub import AudioSegment

with open('../config/config.yml', 'r') as config_file:
    config_data = yaml.safe_load(config_file)

os.environ["OPENAI_API_KEY"] = config_data['openai_api_key']
openai.api_key = os.getenv("OPENAI_API_KEY")

# async def transcribe(filepath, prompt=""):
#     # use openai for transcription
#     file_type = filepath.split(".")[-1]
#     filename = filepath.split(".")[0]
#     # generate unique filename
#     new_filename = str(uuid.uuid4())
#
#     if file_type == "ogg":
#         # convert to wav
#         stream = ffmpeg.input(filepath)
#         stream = ffmpeg.output(stream, new_filename + ".wav")
#         ffmpeg.run(stream)
#
#         # with open(new_filename + ".wav") as file_content:
#         #     print(file_content)
#         #     result = await openai.Audio.transcribe("whisper-1", file_content)
#         #     return result
#         file = open(new_filename + ".wav", 'rb')
#         print(f"prompt is {prompt}")
#         transcript = openai.Audio.transcribe("whisper-1", file, prompt=prompt)
#         return transcript.text
#
#     else:
#         print("file type not supported")
#         return None


# get folder path
folder_path = os.path.dirname(os.path.realpath(__file__)) + "/jobs/"

# Supported formats: ['m4a', 'mp3', 'webm', 'mp4', 'mpga', 'wav', 'mpeg']",
supported_formats = ['m4a', 'mp3', 'webm', 'mp4', 'mpga', 'wav', 'mpeg']


def get_file_size(file_path):
    return os.stat(file_path).st_size / (1024 * 1024)  # size in MB


def split_audio(job_id, max_size):
    file_path = f"jobs/{job_id}/{job_id}.mp3"
    audio = AudioSegment.from_mp3(file_path)

    duration = len(audio)
    fragment_duration = math.ceil(
        (max_size * 1000 * 1024 * 1024) / audio.frame_rate / audio.sample_width / audio.channels)
    fragments = []
    start = 0

    while start < duration:
        end = min(start + fragment_duration, duration)
        fragments.append(audio[start:end])
        start = end

    return fragments


async def convert_media_to_mp3(file_path, output_path):
    input_format = os.path.splitext(file_path)[1][1:]
    AudioSegment.from_file(file_path, input_format).export(output_path, format='mp3')
    return output_path


async def transcribe_and_save(input_path, output_path, output_format, fragment_index, total_fragments):
    # check incoming format is supported

    url = 'https://api.openai.com/v1/audio/transcriptions'
    headers = {'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY']}
    files = {'file': open(input_path, 'rb'),
             'model': (None, 'whisper-1'),
             'response_format': (None, output_format)}
    response = requests.post(url, headers=headers, files=files)

    # output_path = os.path.join(folder_path, os.path.splitext(os.path.basename(file_path_to_transcribe))[0] + '.' + output_format)
    # If it's the first fragment, overwrite the output file, otherwise append to it
    mode = 'w' if fragment_index == 0 else 'a'
    content = response.content.decode('utf-8')
    with open(output_path, mode) as f:
        # Remove the "WEBVTT" header from the response content and write the remaining content
        # content = content.replace("WEBVTT\n\n", "")
        f.write(content)

        # Add an extra newline if it's not the last fragment
        if fragment_index != total_fragments - 1:
            f.write("\n")

    return content


async def process_audio(file_path, prompt="", response_format="vtt", start_with=1, max_size=25):
    # todo add other response formats
    # This function creates separate folders for each job and transcribes the audio file
    job_id = os.path.splitext(os.path.basename(file_path))[0]

    job_folder_path = folder_path + os.path.splitext(os.path.basename(file_path))[0]
    if not os.path.exists(job_folder_path):
        os.makedirs(job_folder_path)

    file_path_to_transcribe = file_path
    output_path = job_folder_path + '/' + job_id + '.vtt'

    if os.path.splitext(file_path)[1][1:] != "mp3":
        print(f"Format {os.path.splitext(file_path)[1][1:]} not supported. Converting to MP3...")
        file_path_to_transcribe = await convert_media_to_mp3(file_path, job_folder_path + '/' + job_id + '.mp3')

    file_size = get_file_size(file_path_to_transcribe)

    print(f"File size of {file_path_to_transcribe} is {file_size} MB")

    if file_size < max_size:
        print(f"Transcribing job {job_id}... Full size")
        # await transcribe_and_save(file_path_to_transcribe, output_path, 'vtt', 0, 1)
        with open(file_path_to_transcribe, 'rb') as audio_file:
            transcript = await openai.Audio.atranscribe("whisper-1", audio_file, prompt=prompt,
                                                       response_format=response_format)
        # save string as vtt file
        with open(output_path, 'w') as f:
            f.write(transcript)
    else:
        print(f"Transcribing job {job_id}... Splitting into fragments")
        # todo provide new file path instead of old
        fragments = split_audio(job_id, max_size)
        total_fragments = len(fragments)

        vtt_transcript_stings = []

        for i, fragment in enumerate(fragments):
            if i + 1 < start_with:
                continue
            audio_path = f"{job_folder_path}/temp_{i}.mp3"
            fragment.export(audio_path, format="mp3")

            print(f"Job id {job_id}. Transcribing fragment {i + 1}/{total_fragments}...")

            with open(audio_path, 'rb') as audio_file:
                vtt_string = await openai.Audio.atranscribe("whisper-1", audio_file, prompt=prompt,
                                                           response_format=response_format)

            vtt_transcript_stings.append(vtt_string)

        print(f"Job id {job_id}. Merging VTT files...")
        merged_string = merge_vtt_strings(vtt_transcript_stings)

        with open(f"{job_folder_path}/{job_id}.vtt", "w") as f:
            f.write(merged_string)

    print(f"Job id {job_id}. Transcribed and saved!")

    vtt_file_path = f"{job_folder_path}/{job_id}.vtt"
    with open(vtt_file_path, 'rb') as f:
        binary = f.read()

    # remove the job folder
    shutil.rmtree(job_folder_path)
    return binary


def merge_vtt_strings(vtt_strings):
    merged_file = "WEBVTT\n\n"
    timestamp_offset = 0

    for vtt_file in vtt_strings:
        lines = vtt_file.strip().split("\n")
        last_end_time = 0

        for index, line in enumerate(lines):
            if index == 0:
                continue  # Skip the "WEBVTT" line

            if "-->" in line:
                start_time, end_time = line.split(" --> ")
                start_time_seconds = convert_vtt_time_to_seconds(start_time)
                end_time_seconds = convert_vtt_time_to_seconds(end_time)

                start_time_seconds += timestamp_offset
                end_time_seconds += timestamp_offset

                start_time = convert_seconds_to_vtt_time(start_time_seconds)
                end_time = convert_seconds_to_vtt_time(end_time_seconds)

                line = f"{start_time} --> {end_time}"
                last_end_time = end_time_seconds

            merged_file += line + "\n"

        timestamp_offset = last_end_time

    return merged_file


def convert_vtt_time_to_seconds(time_str):
    hours, minutes, seconds = map(float, time_str.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def convert_seconds_to_vtt_time(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{seconds:06.3f}"


def sort_filenames(filenames):
    # Define a regular expression pattern to extract the numerical value from the filename
    pattern = re.compile(r'\d+')
    # Define a lambda function to extract the numerical value from the filename and convert it to integer
    key_func = lambda name: int(pattern.findall(name)[0])
    # Sort the list of filenames using the key function
    sorted_filenames = sorted(filenames, key=key_func)
    return sorted_filenames

# file_path = "audio.mp3"
# process_audio(file_path)

# vtt_files = sort_filenames(vtt_files)

# vtt_files = [open(os.path.join("temp_vtt", file), "r").read() for file in vtt_files]


# merged_file = merge_vtt_files(vtt_files)
# print(merged_file)

# save the merged file
