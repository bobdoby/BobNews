import json

DATABASE_FILE = "database.json"


def load_database():

    try:
        with open(DATABASE_FILE, "r") as file:
            return json.load(file)

    except:
        return {}



def save_database(database):

    with open(DATABASE_FILE, "w") as file:
        json.dump(database, file, indent=4)



def get_database():

    return load_database()



def add_game(
    user_id,
    username,
    game_name,
    source_id=None,
    destination_id=None
):

    database = load_database()

    user_id = str(user_id)


    # Create user if they don't exist
    if user_id not in database:

        database[user_id] = {
            "username": username,
            "games": {}
        }


    # Update username if it changed
    database[user_id]["username"] = username


    # Create game if user doesn't have it
    if game_name not in database[user_id]["games"]:

        database[user_id]["games"][game_name] = {
            "source": None,
            "destination": None
        }


    # Update source
    if source_id:

        database[user_id]["games"][game_name]["source"] = source_id


    # Update destination
    if destination_id:

        database[user_id]["games"][game_name]["destination"] = destination_id


    save_database(database)



def remove_game(user_id, game_name):

    database = load_database()

    user_id = str(user_id)


    if user_id in database:

        if game_name in database[user_id]["games"]:

            del database[user_id]["games"][game_name]


            save_database(database)

            return True


    return False