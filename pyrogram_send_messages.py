import asyncio
from datetime import datetime

from telethon import TelegramClient, events, sync
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.functions.messages import UpdateDialogFilterRequest
from telethon.tl.types import DialogFilter
from telethon.tl.types import InputPeerUser

array_of_usernames = ['https://t.me/d33rfox']

username_strings = """https://t.me/das_ist_viking
https://t.me/ochernyi
https://t.me/ymelnykov
https://t.me/self51
https://t.me/kleyster
https://t.me/e11iot
https://t.me/puckipsi
https://t.me/tartil_qil
https://t.me/Mindlick
https://t.me/uktamjon_aka
https://t.me/Agill_89
https://t.me/Abdullayev_Askar
https://t.me/futurefkslaves
https://t.me/PiusKariuki
https://t.me/hfmuzb
https://t.me/measurepro
https://t.me/guluzadef
https://t.me/bdullaev
https://t.me/sikeyee
https://t.me/vitalik_zakharkiv
https://t.me/Owenzbs
https://t.me/Komiljon_Xamidjonov
https://t.me/anasta099
https://t.me/StDinmukhamed
https://t.me/rasimatics
https://t.me/n47_fk
https://t.me/KhumoyunUrinboev
https://t.me/Angry_Uncle
https://t.me/BelieveManasseh
https://t.me/derinmola96
https://t.me/rabu_7
https://t.me/kolyazakharov
https://t.me/zabftft
https://t.me/nnazaryshyn
https://t.me/DanielKurmanaliev
https://t.me/mrRootLog
https://t.me/SerhiyZhyhadlo
https://t.me/mammadaliyevmammadali"""

username_array = username_strings.split('\n')
links_string = """https://www.notion.so/margulan-info/Daniil-48fff71ea67346fc84a3c51c3449d512?pvs=4

https://www.notion.so/margulan-info/Oleh-Chornyi-089eac7005aa46909a1d90b65ac1558b?pvs=4

https://www.notion.so/margulan-info/Yuriy-Melnykov-1554120e5e7546089a629ccdb5ee8291?pvs=4

https://www.notion.so/margulan-info/Roma-Babii-645bd1296d6648dd8e4a557289a30958?pvs=4

https://www.notion.so/margulan-info/b646ac8f1d224584b0f221204da53c98?pvs=4

https://www.notion.so/margulan-info/a6da78909fd24ceb86cb233ab8ae85e0?pvs=4

https://www.notion.so/margulan-info/Mykhailo-Anhelskyi-c110166fa37c4d44a5d4e1d43f81bc7d?pvs=4

https://www.notion.so/margulan-info/ca123ce110d841a1afce0c6e35cb0836?v=fc03a416378446388f077c5170de6c5c&pvs=4#8076269de97f406b8c54450801378de4

https://www.notion.so/margulan-info/ca123ce110d841a1afce0c6e35cb0836?v=fc03a416378446388f077c5170de6c5c&pvs=4#b72d84e52b29402d8cc8ecc608dbb5eb

https://www.notion.so/margulan-info/ca123ce110d841a1afce0c6e35cb0836?v=fc03a416378446388f077c5170de6c5c&pvs=4#da9d2b3326c247b7b72dbfb10654b5a8

https://www.notion.so/margulan-info/ca123ce110d841a1afce0c6e35cb0836?v=fc03a416378446388f077c5170de6c5c&pvs=4#556ac699552b4a4eb19c0107e85a3bb0

https://www.notion.so/margulan-info/ca123ce110d841a1afce0c6e35cb0836?v=fc03a416378446388f077c5170de6c5c&pvs=4#4a55fdbeddd64fc7b08b6e8b7ad451e0

https://www.notion.so/margulan-info/ca123ce110d841a1afce0c6e35cb0836?v=fc03a416378446388f077c5170de6c5c&pvs=4#e31ed8bd2a9c46b99578cc0d8fd1dfdd

https://www.notion.so/margulan-info/ca123ce110d841a1afce0c6e35cb0836?v=fc03a416378446388f077c5170de6c5c&pvs=4#deb19f7e31e44d41b2aa899694bdae73

https://www.notion.so/margulan-info/ca123ce110d841a1afce0c6e35cb0836?v=fc03a416378446388f077c5170de6c5c&pvs=4#1d3d8c82a26641f2b93bafd8a37a33ad

https://www.notion.so/margulan-info/ca123ce110d841a1afce0c6e35cb0836?v=fc03a416378446388f077c5170de6c5c&pvs=4#cf8361a47c1348119cef909962fcedd1

https://www.notion.so/margulan-info/ca123ce110d841a1afce0c6e35cb0836?v=fc03a416378446388f077c5170de6c5c&pvs=4#2a4d08112e9847fda03b879f4cffbaec

https://www.notion.so/margulan-info/ca123ce110d841a1afce0c6e35cb0836?v=fc03a416378446388f077c5170de6c5c&pvs=4#096fc614fe71471ea635b5f3a0125dbf

https://www.notion.so/margulan-info/Rahel-Dires-4558af06783b42dcb60a8e6da57a0956?pvs=4

https://www.notion.so/margulan-info/7f609ed33dbc403fb4e6a703a3c1be90?pvs=4

https://www.notion.so/margulan-info/612a1575c0354e56a156569c05e37d1e?pvs=4

https://www.notion.so/margulan-info/Komiljon-Khamidjonov-0eadd46a03804ae3861e9d6bb5d7c0e9?pvs=4

https://www.notion.so/margulan-info/Anastasiia-Abramova-7fbe0e724f1e47b9b75d3120dd94e355?pvs=4

https://www.notion.so/margulan-info/Din-Stamaly-38163dbf6f76457c84d24105b4ff2b99?pvs=4

https://www.notion.so/margulan-info/Rasim-Mammadov-853e89f842eb41b3a2cebf0816681726?pvs=4

https://www.notion.so/margulan-info/Natnael-Tilahun-0f4879b295b94ec4ac54cedda123364b?pvs=4

https://www.notion.so/margulan-info/Khumoyun-Urinboev-c068121f045f49f1a247ad6878e1303d?pvs=4

https://www.notion.so/margulan-info/ddb1983e3aaa404186a1fa22f4fcc5d6?pvs=4

https://www.notion.so/margulan-info/Believe-Amadi-1f8554976fc840b1b841f8b389027876?pvs=4

https://www.notion.so/margulan-info/Aderinmola-Ojedokun-e676b46f9a144d7b9dde8d93166f52d2?pvs=4

https://www.notion.so/margulan-info/Biruk-Alamirew-ff119b6549d84053b8c2321ca778d3ed?pvs=4

https://www.notion.so/margulan-info/Kolya-Zakharov-97e69010a7ad4ffb8a91cbc9fbaeed3d?pvs=4

https://www.notion.so/margulan-info/Vlad-Zabolotnyi-aa7b933190954d318e2f132f90b0bd1e?pvs=4

https://www.notion.so/margulan-info/0b6be33427634331be45592b4158f5e2?pvs=4

https://www.notion.so/margulan-info/Daniel-Kurmanaliev-31c3a67eeac346bb97f843dad2a06b85?pvs=4

https://www.notion.so/margulan-info/Yalchin-Mammadli-c8b06ab4cc2241308487a524c70773a7?pvs=4

https://www.notion.so/margulan-info/a20f1c2e7cc84986b91a43abaaec7742?pvs=4

https://www.notion.so/margulan-info/Mammadali-Mammadaliyev-ba213f4b949c44308b36d3"""
# make array of links by splitting by \n
links_array = links_string.split("\n\n")
# remove "\n" from each of them


# make array of dicts. match username and link by index. username and links are separate arrays
array_of_people_dicts = []
print(len(links_array))
print(len(username_array))
for i in range(len(links_array)):
    username = username_array[i]
    link = links_array[i]
    array_of_people_dicts.append({"username": username, "link": link})

# delete last element of array if it is empty
if array_of_people_dicts[-1]["username"] == "":
    array_of_people_dicts.pop(-1)

# array_of_people_dicts = [{'username': 'https://t.me/d33rfox', 'link': 'https://www.notion.so/margulan-info/Daniil-48fff71ea67346fc84a3c51c3449d512?pvs=4'}]
print(array_of_people_dicts)

def insert_link(link):
    return f"""👋 Greetings,

I am contacting you regarding a role of a developer within our R&D team at Margulan.Info. We appreciate your interest in our venture and your passion for artificial intelligence.

We receive a high number of responses daily, and your comprehensive response will help us to determine if you share our team's values and mission. This will be beneficial for both of us, as it saves time.

To ensure a potential mutual fit, I would like to gather some insights from you on the following aspects: **Motivation for the Position** and **Skills and Experience**

Please, keep your answer short. The shorter, the better. Please, do not use ChatGPT to generate your answers. You can just write bullet points on why you are interested in this position and what skills you have.

Here is the link to the form: {link}. If you don't have access to it, or there are any issues, please let us know."""


api_id=20282180
api_hash="a1264d4ca1cc770ed1ed1bee674ab46a"



# These example values won't work. You must get your own api_id and
# api_hash from https://my.telegram.org, under API Development.

client = TelegramClient('session_name', api_id, api_hash)
client.start()


async def send_message_to_user(user_ditc, folder):
    username = user_ditc['username'].split("/")[-1]
    # check if our chat is empty
    messages = client.iter_messages(username, limit=10)
    is_empty = True
    async for message in messages:
        is_empty = False
        break

    if not is_empty:
        print(f"Chat with {username} is not empty")
        return

    message_to_send = insert_link(user_ditc['link'])

    await client.send_message(username, message_to_send)
    user = await client.get_entity(username)
    include_peers = folder.include_peers
    new_peer = InputPeerUser(user.id, user.access_hash)
    include_peers.append(new_peer)
    # add user to folder
    result = await client(UpdateDialogFilterRequest(
        id=folder.id,
        filter=DialogFilter(
            id=folder.id,
            title=folder.title,
            include_peers=include_peers,
            exclude_peers=folder.exclude_peers,
            pinned_peers=folder.pinned_peers,
            contacts=folder.contacts,
            non_contacts=folder.non_contacts,
            groups=folder.groups,
            broadcasts=folder.broadcasts,
            bots=folder.bots,
            exclude_muted=folder.exclude_muted,
            exclude_read=folder.exclude_read,
            exclude_archived=folder.exclude_archived,
            emoticon=folder.emoticon,
        )))


async def main():
    # send messages to all users in array_of_usernames
    current_time = datetime.utcnow()
    natural_language_time = current_time.strftime("%H:%M")
    # wait 0.5 seconds between each message
    # get telegram account folders
    result = await client(GetDialogFiltersRequest())
    folder = None
    for x in result:
        has_title = hasattr(x, 'title')
        if (has_title and x.title == "Auto Send 📥"):
            folder = x
            break

    if (folder is None):
        print("No folder found")
        return

    for user_ditc in array_of_people_dicts:
        await send_message_to_user(user_ditc, folder)

        await asyncio.sleep(1.5)


with client:
    client.loop.run_until_complete(main())

