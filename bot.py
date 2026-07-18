import os
import discord
from loot_database import load_loot_database
from discord import app_commands
import logging
import json
import difflib
from dotenv import load_dotenv
from database import get_database, add_game, remove_game


load_dotenv()




logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("GameNewsBot")


FORWARDED_FILE = "forwarded_messages.json"


def load_forwarded_messages():
    try:
        with open(FORWARDED_FILE, "r") as file:
            return set(json.load(file))
    except:
        return set()


def save_forwarded_messages(messages):
    with open(FORWARDED_FILE, "w") as file:
        json.dump(list(messages), file)


forwarded_messages = load_forwarded_messages()


TOKEN = os.getenv("DISCORD_TOKEN")


intents = discord.Intents.default()
intents.message_content = True


class GameNewsClient(discord.Client):

    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)


client = GameNewsClient()


try:
    loot_database = load_loot_database()
    logger.info(
        f"Loaded {len(loot_database)} loot items"
    )

except Exception as e:
    logger.error(
        f"Failed to load loot database: {e}"
    )

    loot_database = {}



#========================
# Location Formatter
#========================

def format_locations(data):

    text = ""

    for location in data["locations"]:

        text += f"**{location['town']}**"

        if location.get("amount"):
            text += f" — {location['amount']} found"

        text += "\n"

        if location["details"]:

            for detail in location["details"]:
                text += f"└ {detail}\n"

        else:

            text += "└ No additional details\n"


    return text

#========================
#Loot Buttons
#=======================

class LootButtons(discord.ui.View):

    def __init__(self, item, data, colour):
        super().__init__(timeout=60)

        self.item = item
        self.data = data
        self.colour = colour


        # Remove buttons that are not needed

        if not data["locations"]:
            self.remove_item(self.locations)

        if not data["crafting"]:
            self.remove_item(self.crafting)


    @discord.ui.button(
        label="📍 Locations",
        style=discord.ButtonStyle.green
    )
    async def locations(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        text = format_locations(self.data)

        embed = discord.Embed(
            title=f"📍 Locations - {self.item}",
            description=text,
            colour=self.colour
        )


        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )



    @discord.ui.button(
        label="⚙️ Crafting",
        style=discord.ButtonStyle.blurple
    )
    async def crafting(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        text = ""

        for recipe in self.data["crafting"]:

            text += (
                f"**📍 {recipe['town']}**\n"
            )

            text += "Input:\n"

            for ingredient in recipe["inputs"]:

                text += (
                    f"└ {ingredient['amount']}x "
                    f"{ingredient['item']}\n"
                )


            text += "Output:\n"

            text += (
                f"└ {recipe['output_amount']}x "
                f"{self.item}\n\n"
            )


        embed = discord.Embed(
            title=f"⚙️ Crafting - {self.item}",
            description=text,
            colour=self.colour
        )


        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

 #========================
 #SandSearch Command
 #========================

@client.tree.command(
    name="sandsearch",
    description="Search Sand loot locations"
)
async def sandsearch(
    interaction: discord.Interaction,
    item: str
):

    search = item.upper()

    result = None


    # Exact / partial match first
    for name, data in loot_database.items():

        if search in name.upper():

            result = data
            item = name
            break



    # Fuzzy match if nothing found
    if result is None:

        matches = difflib.get_close_matches(
            search,
            loot_database.keys(),
            n=1,
            cutoff=0.6
        )


        if matches:

            item = matches[0]
            result = loot_database[item]


    if result is None:

        await interaction.response.send_message(
            f"❌ Could not find **{item}**"
        )

        return


    rarity_colors = {
        "COMMON": discord.Colour.greyple(),
        "UNCOMMON": discord.Colour.green(),
        "RARE": discord.Colour.blue(),
        "NOTEWORTHY": discord.Colour.purple(),
        "REMARKABLE": discord.Colour.orange(),
        "EXPERIMENTAL": discord.Colour.red()
    }


    rarity = result.get("rarity")


    if isinstance(rarity, str):

        colour = rarity_colors.get(
            rarity.upper(),
            discord.Colour.blue()
        )

    else:

        colour = discord.Colour.blue()


    embed = discord.Embed(
        title=f"🔎 {item}",
        colour=colour
    )


    price = result.get("price")

    if price and str(price).lower() != "nan":

        embed.add_field(
            name="💰 Price",
            value=str(price),
            inline=True
        )


    if result["rarity"]:

        embed.add_field(
            name="⭐ Rarity",
            value=result["rarity"],
            inline=True
        )

    has_price = (
        result.get("price") is not None
        and str(result.get("price")).lower() != "nan"
    )

    has_rarity = (
        isinstance(result.get("rarity"), str)
        and result.get("rarity").strip() != ""
    )

    has_crafting = bool(result.get("crafting"))

    has_extra_info = has_price or has_rarity or has_crafting


    if not has_extra_info and result.get("locations"):

        text = format_locations(result)

        embed.add_field(
            name="📍 Found Locations",
            value=text,
            inline=False
        )


    


    if has_extra_info:

        await interaction.response.send_message(
            embed=embed,
            view=LootButtons(item, result, colour)
        )

    else:

        await interaction.response.send_message(
            embed=embed
        )



#========================
#SandSearch Autocomplete
#========================


@sandsearch.autocomplete("item")
async def sandsearch_autocomplete(
    interaction: discord.Interaction,
    current: str
):

    choices = []

    current = current.upper()


    for item in loot_database.keys():

        if current in item:

            choices.append(
                app_commands.Choice(
                    name=item,
                    value=item
                )
            )


    return choices[:25]



@client.event
async def on_ready():

    synced = await client.tree.sync()

    logger.info("=" * 40)
    logger.info(f"Logged in as {client.user}")
    logger.info(f"Synced {len(synced)} global commands")
    logger.info("=" * 40)



@client.event
async def on_message(message):

    print("========== MESSAGE RECEIVED ==========")
    print(f"Author: {message.author}")
    print(f"Channel: {message.channel}")
    print(f"Type: {message.type}")
    print(f"Flags: {message.flags}")
    print(f"Content: {message.content}")
    print(f"Embeds: {len(message.embeds)}")
    print(f"Attachments: {len(message.attachments)}")
    print(f"Channel ID: {message.channel.id}")
    print(f"Message ID: {message.id}")
    print("======================================")

    if message.author.bot:
        return

    if message.guild is None:
        return


    if message.id in forwarded_messages:

        logger.info(
            f"Ignored duplicate message {message.id}"
        )

        return


    database = get_database()


    game = None
    destination_id = None


    for user_id, user_data in database.items():

        for name, channels in user_data.get("games", {}).items():

            if message.channel.id == channels.get("source"):

                game = name
                destination_id = channels.get("destination")
                break


        if game:
            break



    if destination_id is None:

        logger.warning(
            f"{game} has no destination set yet"
        )

        return



    thread = client.get_channel(destination_id)


    if thread is None:

        logger.error(
            f"Could not find destination for {game}"
        )

        return



    await thread.send(
        content=f"## 📰 {game} Update\n\n{message.content}",
        embeds=message.embeds,
        files=[
            await attachment.to_file()
            for attachment in message.attachments
        ]
    )


    forwarded_messages.add(message.id)
    save_forwarded_messages(forwarded_messages)


    logger.info(
        f"Forwarded {game} update"
    )

#========================
# SandRefresh Command
#========================

@client.tree.command(
    name="sandrefresh",
    description="Reload the Sand loot database"
)
@app_commands.checks.has_permissions(manage_guild=True)
async def sandrefresh(
    interaction: discord.Interaction
):

    global loot_database

    await interaction.response.defer(
        ephemeral=True
    )

    try:

        loot_database = load_loot_database()

        logger.info(
            f"Reloaded loot database: {len(loot_database)} items"
        )

        await interaction.followup.send(
            f"✅ Sand database refreshed!\n"
            f"📦 Loaded **{len(loot_database)} items**",
            ephemeral=True
        )


    except Exception as e:

        logger.error(
            f"Failed to refresh loot database: {e}"
        )

        await interaction.followup.send(
            f"❌ Failed to refresh database:\n`{e}`",
            ephemeral=True
        )

#========================
#Send Command
#========================


@client.tree.command(
    name="send",
    description="Register this channel as a game news source"
)
@app_commands.checks.has_permissions(manage_guild=True)
async def send(
    interaction: discord.Interaction,
    game: str
):

    add_game(
        user_id=interaction.user.id,
        username=interaction.user.display_name,
        game_name=game,
        source_id=interaction.channel.id
    )


    await interaction.response.send_message(
        f"✅ Source registered for **{game}**\n"
        f"Channel: {interaction.channel.mention}"
    )

#========================
#Recieve Command
#========================


@client.tree.command(
    name="receive",
    description="Register this thread as a game news destination"
)
@app_commands.checks.has_permissions(manage_guild=True)
async def receive(
    interaction: discord.Interaction,
    game: str
):

    add_game(
        user_id=interaction.user.id,
        username=interaction.user.display_name,
        game_name=game,
        destination_id=interaction.channel.id
    )


    await interaction.response.send_message(
        f"✅ Destination registered for **{game}**\n"
        f"Thread: {interaction.channel.mention}"
    )

@receive.autocomplete("game")
async def receive_autocomplete(
    interaction: discord.Interaction,
    current: str
):

    database = get_database()

    choices = []

    user_id = str(interaction.user.id)

    user_data = database.get(user_id)


    if not user_data:
        return choices


    for game in user_data.get("games", {}):

        if current.lower() in game.lower():

            choices.append(
                app_commands.Choice(
                    name=game,
                    value=game
                )
            )


    return choices[:25]


#========================
#Links Command
#========================


@client.tree.command(
    name="links",
    description="Show all connected game feeds"
)
async def links(
    interaction: discord.Interaction
):

    database = get_database()


    if not database:

        await interaction.response.send_message(
            "No game feeds are currently configured."
        )

        return



    embed = discord.Embed(
        title="📡 Game News Relay",
        description="Current connected feeds",
        colour=discord.Colour.blue()
    )


    for game, channels in database.items():

        source = channels.get("source")
        destination = channels.get("destination")


        value = ""


        if source:
            value += f"📥 Source: <#{source}>\n"


        if destination:
            value += f"📤 Destination: <#{destination}>\n"


        if not value:
            value = "⚠️ Incomplete setup"



        embed.add_field(
            name=f"🎮 {game}",
            value=value,
            inline=False
        )



    await interaction.response.send_message(
        embed=embed
    )

#========================
#Remove Command
#========================



@client.tree.command(
    name="remove",
    description="Remove a game news link"
)
@app_commands.checks.has_permissions(manage_guild=True)
async def remove(
    interaction: discord.Interaction,
    game: str
):

    removed = remove_game(
        interaction.user.id,
        game
    )



    if removed:

        await interaction.response.send_message(
            f"✅ Removed **{game}** from the news relay."
        )

    else:

        await interaction.response.send_message(
            f"❌ Could not find **{game}**."
        )

       
       
#========================
#Remove Autocorrect
#========================

@remove.autocomplete("game")
async def remove_autocomplete(
    interaction: discord.Interaction,
    current: str
):

    database = get_database()

    choices = []

    user_id = str(interaction.user.id)

    user_data = database.get(user_id)


    if not user_data:
        return choices


    for game in user_data["games"].keys():

        if current.lower() in game.lower():

            choices.append(
                app_commands.Choice(
                    name=game,
                    value=game
                )
            )


    return choices[:25]


#========================
#Status Command
#========================

@client.tree.command(
    name="status",
    description="Show the current relay status"
)
async def status(
    interaction: discord.Interaction
):

    database = get_database()

    user_id = str(interaction.user.id)

    user_data = database.get(user_id)


    if not user_data:

        await interaction.response.send_message(
            "No game feeds are currently configured."
        )

        return



    embed = discord.Embed(
        title="📡 Game News Relay Status",
        description=f"Configured by {user_data.get('username')}",
        colour=discord.Colour.green()
    )


    for game, channels in user_data["games"].items():

        value = ""


        source_id = channels.get("source")
        destination_id = channels.get("destination")


        if source_id:

            value += f"📥 Source: <#{source_id}>\n"

        else:

            value += "📥 Source: ❌ Not set\n"



        if destination_id:

            value += f"📤 Destination: <#{destination_id}>\n"

        else:

            value += "📤 Destination: ❌ Not set\n"



        if source_id and destination_id:

            icon = "✅"

        else:

            icon = "⚠️"



        embed.add_field(
            name=f"{icon} {game}",
            value=value,
            inline=False
        )



    await interaction.response.send_message(
        embed=embed
    )


@client.tree.error
async def on_app_command_error(
    interaction,
    error
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        await interaction.response.send_message(
            "❌ You need the **Manage Server** permission to use this command.",
            ephemeral=True
        )

    else:

        raise error


client.run(TOKEN)