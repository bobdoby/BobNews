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



def add_game(game_name, source_id=None, destination_id=None):

    database = load_database()


    if game_name not in database:
        database[game_name] = {}


    if source_id:
        database[game_name]["source"] = source_id


    if destination_id:
        database[game_name]["destination"] = destination_id


    save_database(database)



def remove_game(game_name):

    database = load_database()


    if game_name in database:

        del database[game_name]

        save_database(database)

        return True


    return False