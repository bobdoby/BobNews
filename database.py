import json
import os

DATABASE_FILE = "database.json"


def load_database():

    if not os.path.exists(DATABASE_FILE):
        return {}

    try:

        with open(DATABASE_FILE, "r") as file:
            database = json.load(file)

    except Exception:

        return {}


    # Automatic migration
    changed = False


    for user_id, user_data in database.items():

        if "games" not in user_data:
            continue


        for game, data in user_data["games"].items():


            # Convert old destination format
            if "destination" in data:

                old_destination = data.pop("destination")

                data["destinations"] = []

                if old_destination:

                    data["destinations"].append(
                        old_destination
                    )

                changed = True


            # Ensure destinations exists
            if "destinations" not in data:

                data["destinations"] = []

                changed = True



    if changed:

        save_database(database)


    return database



def save_database(database):

    with open(DATABASE_FILE, "w") as file:

        json.dump(
            database,
            file,
            indent=4
        )



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


    # Create user
    if user_id not in database:

        database[user_id] = {
            "username": username,
            "games": {}
        }


    # Update username
    database[user_id]["username"] = username



    # Create game
    if game_name not in database[user_id]["games"]:

        database[user_id]["games"][game_name] = {
            "source": None,
            "destinations": []
        }



    game = database[user_id]["games"][game_name]



    # Add source
    if source_id:

        game["source"] = source_id



    # Add destination
    if destination_id:

        if destination_id not in game["destinations"]:

            game["destinations"].append(
                destination_id
            )



    save_database(database)



def remove_destination(
    user_id,
    game_name,
    destination_id
):

    database = load_database()

    user_id = str(user_id)


    if user_id not in database:

        return False



    games = database[user_id].get(
        "games",
        {}
    )


    if game_name not in games:

        return False



    destinations = games[game_name].get(
        "destinations",
        []
    )



    if destination_id in destinations:

        destinations.remove(
            destination_id
        )


        save_database(database)

        return True



    return False