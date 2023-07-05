import openai
import tiktoken
import re
import json
import ast

openai.api_key = "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"


# input - file name as string, output - list of dicts {{name:"", timestamp:""}}
def parse_transcript(file_to_segment):
    with open(file_to_segment, 'r', encoding='utf-8') as f:
        transcript = f.read()
    # Split the transcript into lines
    lines = transcript.strip().split('\n')

    chapters = []
    timestamp = ""  # Initialize timestamp
    for line in lines:
        if line == 'WEBVTT' or line.strip() == '':  # Skip the "WEBVTT" line and any empty lines
            continue

        if re.match('\d\d:\d\d:\d\d.\d\d\d --> \d\d:\d\d:\d\d.\d\d\d', line):  # Check if the line is a timestamp line
            timestamp = line[:8]  # Extract the first 6 digits of the timestamp
        else:
            chapters.append({"name": line, "timestamp": timestamp})  # This is a text line, so we create a new chapter with the current timestamp and text
    return chapters


# input - file name as string, output - paragraphs of text
def parse_transcript_paragraphs(file_to_segment):
    chapters = parse_transcript(file_to_segment)  # Creates dicts {chapter{name:"", timestamp:""}}
    chapter_texts = [chapter["name"] for chapter in chapters]  # Extract the chapter names
    text = ' '.join(chapter_texts)  # Concatenate chapter names into a single string
    chunks = get_chunks(text)  # Chunks text

    responses = []
    for chunk in chunks:
        message1 = {"role": "system",
                    "content": "You should analyze the provided text and put punctuation marks where needed. Reply with the fixed sentences."}
        message2 = {"role": "user", "content": chunk['content']}
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-16k",  # update with the model you're using
            messages=[message1, message2]
        )
        print(response)
        responses.append(response.choices[0].message.content.strip())
    # TODO second call to create paragraphs
    print("Writing paragraphs to file...")
    with open("AI unlocked full paragraphs.txt", "w") as f:
        f.write("\n".join(responses))
    print("File written successfully.")


# counts number of tokens
def num_tokens_from_string(string: str, encoding_name: str) -> int:
    # Returns the number of tokens in a text string.
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


# outputs list of dictionaries [{"content": ""}], 5k tokens each
def get_chunks(text):
    words = text.split(' ')
    chunks = []
    chunk = ""
    while words:
        temp_chunk = chunk + ' ' + words[0]
        num_tokens = num_tokens_from_string(temp_chunk, "cl100k_base")  # counts tokens
        if num_tokens <= 5000:
            chunk = temp_chunk
            words.pop(0)
        else:
            chunks.append({"content": chunk.strip()})
            chunk = ""
    if chunk:  # Append any remaining chunk
        chunks.append({"content": chunk.strip()})
    return chunks


# input - file name as string, output - json array [{"start_time":"", "chapter_name":"", "content":""}]
def main(file_to_segment):
    with open(file_to_segment, "r", encoding="utf-8") as f:
        text = f.read()
    chunks = get_chunks(text)
    responses = []
    for chunk in chunks:
        print("Sending call to OpenAI")
        message1 = {"role": "system", "content": """
ROLE: Creating chapter from transcripts
Output format: JSON
Output language: This should be the same as the input language. IT IS VERY IMPORTANT
1. Identify language
2. Provide JSON, do not provide text, only "start_time" and "chapter_name".
Example output:
The received text is in English. Therefore I should write a response in English.
[{
"start_time": "00:00",
"chapter_name": "Introduction: How to take smart notes."
},
{
"start_time": "04:00",
"chapter_name": "What is a note?"
},
{
"start_time": "08:00",
"chapter_name": "Should you take notes?"
}]
        """}
        message2 = {"role": "user", "content": chunk['content']}
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-16k",  # update with the model you're using
            messages=[message1, message2]
        )
        print(response)

        # Parse the content of the response to a dictionary
        response_content = json.loads(response.choices[0].message.content.strip())
        # Add the API response to the responses list
        responses.append(response_content)

    print("Writing chunks to file...")
    with open("AI_unlocked_full_chaptered.json", "w", encoding="utf-8") as f:
        json.dump(responses, f, ensure_ascii=False, indent=4)
    print("File written successfully.")


# parse_transcript_paragraphs("AI unlocked full.txt")

if __name__ == "__main__":
    main("AI unlocked full.txt")
