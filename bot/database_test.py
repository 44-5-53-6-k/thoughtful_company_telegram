from datetime import datetime
from database import Database

import config


def main():
    database = Database()
    new_user_id = 1
    chat_id = 1
    database.add_new_user(user_id=new_user_id, chat_id=chat_id, username="username", first_name="first_name",
                          last_name="last_name")
    database.check_if_user_exists(user_id=new_user_id, raise_exception=True)
    dialog_id = database.start_new_dialog(user_id=new_user_id)
    database.set_dialog_messages(
        user_id=new_user_id,
        dialog_messages=[{"user": "sample_user_id", "bot": "answer", "date": datetime.now()}],
        dialog_id=dialog_id
    )
    database.get_dialog_messages(user_id=new_user_id, dialog_id=dialog_id)
    database.log_message(
        new_user_id,
        message={
            "status": "read",
            "text": "text",
            "date": datetime.now()
        },
        dialog_id=dialog_id,
    )


# call main
if __name__ == "__main__":
    main()
