import os
import discord
from discord import app_commands
import logging
import json
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



@client.event
async def on_ready():

    synced = await client.tree.sync()

    logger.info("=" * 40)
    logger.info(f"Logged in as {client.user}")
    logger.info(f"Synced {len(synced)} global commands")
    logger.info("=" * 40)



@client.event
async def on_message(message):

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


    for name, channels in database.items():

        if message.channel.id == channels.get("source"):

            game = name
            destination_id = channels.get("destination")
            break



    if game is None:
        return



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
        game_name=game,
        source_id=interaction.channel.id
    )


    await interaction.response.send_message(
        f"✅ Source registered for **{game}**\n"
        f"Channel: {interaction.channel.mention}"
    )





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

    for game, channels in database.items():

        # Only show games without a destination
        if channels.get("destination"):
            continue

        if current.lower() in game.lower():

            choices.append(
                app_commands.Choice(
                    name=game,
                    value=game
                )
            )

    return choices[:25]





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





@client.tree.command(
    name="remove",
    description="Remove a game news link"
)
@app_commands.checks.has_permissions(manage_guild=True)
async def remove(
    interaction: discord.Interaction,
    game: str
):

    removed = remove_game(game)



    if removed:

        await interaction.response.send_message(
            f"✅ Removed **{game}** from the news relay."
        )

    else:

        await interaction.response.send_message(
            f"❌ Could not find **{game}**."
        )

@remove.autocomplete("game")
async def remove_autocomplete(
    interaction: discord.Interaction,
    current: str
):

    database = get_database()

    choices = []

    for game in database.keys():

        if current.lower() in game.lower():

            choices.append(
                app_commands.Choice(
                    name=game,
                    value=game
                )
            )

    return choices[:25]


@client.tree.command(
    name="status",
    description="Show the current relay status"
)
async def status(
    interaction: discord.Interaction
):

    database = get_database()


    if not database:

        await interaction.response.send_message(
            "No game feeds are currently configured."
        )

        return



    embed = discord.Embed(
        title="📡 Game News Relay Status",
        description="Current relay configuration",
        colour=discord.Colour.green()
    )


    for game, channels in database.items():

        source_id = channels.get("source")
        destination_id = channels.get("destination")


        value = ""


        # Check source
        if source_id:

            source = client.get_channel(source_id)

            if source:
                value += f"📥 Source: {source.mention}\n"
            else:
                value += f"📥 Source: ⚠️ Channel missing\n"

        else:

            value += "📥 Source: ❌ Not set\n"



        # Check destination
        if destination_id:

            destination = client.get_channel(destination_id)

            if destination:
                value += f"📤 Destination: {destination.mention}\n"
            else:
                value += f"📤 Destination: ⚠️ Channel missing\n"

        else:

            value += "📤 Destination: ❌ Not set\n"



        # Status indicator

        if source_id and destination_id:

            status_icon = "✅"

        else:

            status_icon = "⚠️"



        embed.add_field(
            name=f"{status_icon} {game}",
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