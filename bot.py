import difflib
import json
import logging
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

from database import add_game, get_database, remove_destination
from loot_database import load_loot_database


load_dotenv()
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logging.getLogger("dropbox").setLevel(logging.WARNING)
logger = logging.getLogger("GameNewsBot")

FORWARDED_FILE = "forwarded_messages.json"
TOKEN = os.getenv("DISCORD_TOKEN")


def load_forwarded_messages():
    try:
        with open(FORWARDED_FILE, "r", encoding="utf-8") as file:
            return set(json.load(file))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_forwarded_messages(messages):
    with open(FORWARDED_FILE, "w", encoding="utf-8") as file:
        json.dump(list(messages), file)


def format_amount(value):
    """Display whole-number values without a trailing .0."""
    if value is None:
        return None

    value_as_text = str(value)
    if value_as_text.endswith(".0"):
        return str(int(float(value_as_text)))
    return value_as_text


def format_locations(data):
    text = ""

    for location in data.get("locations", []):
        town = location.get("town") or "Unknown location"
        text += f"**{town}**"

        amount = format_amount(location.get("amount"))
        if amount:
            text += f" — {amount} found"

        text += "\n"

        details = location.get("details", [])
        if details:
            for detail in details:
                text += f"└ {detail}\n"
        else:
            text += "└ No additional details\n"

        text += "\n"

    return text or "No locations recorded."


def format_crafting(item, data):
    text = ""

    for recipe in data.get("crafting", []):
        town = recipe.get("town") or "Unknown location"
        text += f"**{town}**\nInput:\n"

        inputs = recipe.get("inputs", [])
        if inputs:
            for ingredient in inputs:
                amount = format_amount(ingredient.get("amount")) or "?"
                text += f"└ {amount}x {ingredient.get('item', 'Unknown item')}\n"
        else:
            text += "└ No input recorded\n"

        output_amount = format_amount(recipe.get("output_amount")) or "?"
        text += f"Output:\n└ {output_amount}x {item}\n\n"

    return text or "No crafting recipe recorded."


intents = discord.Intents.default()
intents.message_content = True


class GameNewsClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)


client = GameNewsClient()

relay_group = app_commands.Group(
    name="relay",
    description="Manage game news relays",
)
client.tree.add_command(relay_group)

forwarded_messages = load_forwarded_messages()

try:
    loot_database = load_loot_database()
    logger.info("Loaded %s loot items", len(loot_database))
except Exception as error:
    logger.error("Failed to load loot database: %s", error)
    loot_database = {}


class LootButtons(discord.ui.View):
    def __init__(self, item, data, colour):
        super().__init__(timeout=60)
        self.item = item
        self.data = data
        self.colour = colour

        if not data.get("locations"):
            self.remove_item(self.locations)
        if not data.get("crafting"):
            self.remove_item(self.crafting)

    @discord.ui.button(label="📍 Locations", style=discord.ButtonStyle.green)
    async def locations(self, interaction, button):
        embed = discord.Embed(
            title=f"📍 Locations - {self.item}",
            description=format_locations(self.data)[:4096],
            colour=self.colour,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="⚙️ Crafting", style=discord.ButtonStyle.blurple)
    async def crafting(self, interaction, button):
        embed = discord.Embed(
            title=f"⚙️ Crafting - {self.item}",
            description=format_crafting(self.item, self.data)[:4096],
            colour=self.colour,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


@client.tree.command(name="sandsearch", description="Search Sand loot locations")
async def sandsearch(interaction: discord.Interaction, item: str):
    search = item.upper()
    matched_item = None
    result = None

    for name, data in loot_database.items():
        if search in name.upper():
            matched_item = name
            result = data
            break

    if result is None:
        matches = difflib.get_close_matches(search, loot_database.keys(), n=1, cutoff=0.6)
        if matches:
            matched_item = matches[0]
            result = loot_database[matched_item]

    if result is None:
        await interaction.response.send_message(f"❌ Could not find **{item}**")
        return

    rarity_colours = {
        "COMMON": discord.Colour.greyple(),
        "UNCOMMON": discord.Colour.green(),
        "RARE": discord.Colour.blue(),
        "NOTEWORTHY": discord.Colour.purple(),
        "REMARKABLE": discord.Colour.orange(),
        "EXPERIMENTAL": discord.Colour.red(),
    }
    rarity = result.get("rarity")
    colour = rarity_colours.get(str(rarity).upper(), discord.Colour.blue())

    embed = discord.Embed(title=f"🔎 {matched_item}", colour=colour)

    print(result)
    ###################################################################################
    price = result.get("price")
    if price is not None and str(price).lower() != "nan":
        embed.add_field(name="💰 Price", value=format_amount(price), inline=True)

    if rarity and str(rarity).lower() != "nan":
        embed.add_field(name="⭐ Rarity", value=str(rarity), inline=True)

    category = result.get("category")

    if category and str(category).lower() != "nan":
        embed.add_field(
            name="📦 Category",
            value=str(category),
            inline=True
        )

    has_extra_info = (
        bool(price)
        or bool(rarity)
        or bool(category)
        or bool(result.get("crafting"))
    )

    if not has_extra_info and result.get("locations"):
        embed.add_field(
            name="📍 Found Locations",
            value=format_locations(result)[:1024],
            inline=False,
        )

    view = LootButtons(matched_item, result, colour)

    if view.children:
        await interaction.response.send_message(
            embed=embed,
            view=view
        )
    else:
        await interaction.response.send_message(
            embed=embed
        )


@sandsearch.autocomplete("item")
async def sandsearch_autocomplete(interaction: discord.Interaction, current: str):
    current = current.upper()
    return [
        app_commands.Choice(name=item, value=item)
        for item in loot_database
        if current in item.upper()
    ][:25]


@client.tree.command(name="sandrefresh", description="Reload the Sand loot database")
@app_commands.checks.has_permissions(manage_guild=True)
async def sandrefresh(interaction: discord.Interaction):
    global loot_database
    await interaction.response.defer(ephemeral=True)

    try:
        loot_database = load_loot_database()
        logger.info("Reloaded loot database: %s items", len(loot_database))
        await interaction.followup.send(
            f"✅ Sand database refreshed!\n📦 Loaded **{len(loot_database)} items**",
            ephemeral=True,
        )
    except Exception as error:
        logger.error("Failed to refresh loot database: %s", error)
        await interaction.followup.send(
            f"❌ Failed to refresh database:\n`{error}`",
            ephemeral=True,
        )


def get_user_games(interaction: discord.Interaction):
    user_data = get_database().get(str(interaction.user.id), {})
    return user_data.get("games", {})


@relay_group.command(name="send", description="Register this channel as a game news source")
@app_commands.checks.has_permissions(manage_guild=True)
async def relay_send(interaction: discord.Interaction, game: str):
    add_game(
        user_id=interaction.user.id,
        username=interaction.user.display_name,
        game_name=game,
        source_id=interaction.channel.id,
    )
    await interaction.response.send_message(
        f"✅ Source registered for **{game}**\nChannel: {interaction.channel.mention}"
    )


@relay_group.command(name="receive", description="Add this channel or thread as a news destination")
@app_commands.checks.has_permissions(manage_guild=True)
async def relay_receive(interaction: discord.Interaction, game: str):
    add_game(
        user_id=interaction.user.id,
        username=interaction.user.display_name,
        game_name=game,
        destination_id=interaction.channel.id,
    )
    await interaction.response.send_message(
        f"✅ Destination added for **{game}**\nChannel: {interaction.channel.mention}"
    )


@relay_receive.autocomplete("game")
async def relay_receive_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=game, value=game)
        for game in get_user_games(interaction)
        if current.lower() in game.lower()
    ][:25]


@relay_group.command(name="remove", description="Remove this channel as a game news destination")
@app_commands.checks.has_permissions(manage_guild=True)
async def relay_remove(interaction: discord.Interaction, game: str):
    removed = remove_destination(
        user_id=interaction.user.id,
        game_name=game,
        destination_id=interaction.channel.id,
    )

    if removed:
        await interaction.response.send_message(
            f"✅ Removed this channel from **{game}** destinations."
        )
    else:
        await interaction.response.send_message(
            f"❌ This channel is not a destination for **{game}**.",
            ephemeral=True,
        )


@relay_remove.autocomplete("game")
async def relay_remove_autocomplete(interaction: discord.Interaction, current: str):
    current_channel_id = interaction.channel.id
    return [
        app_commands.Choice(name=game, value=game)
        for game, data in get_user_games(interaction).items()
        if current_channel_id in data.get("destinations", [])
        and current.lower() in game.lower()
    ][:25]


@relay_group.command(name="status", description="Show your current relay configuration")
async def relay_status(interaction: discord.Interaction):
    database = get_database()
    user_data = database.get(str(interaction.user.id))

    if not user_data or not user_data.get("games"):
        await interaction.response.send_message("No game relays are currently configured.")
        return

    embed = discord.Embed(
        title="📡 Game News Relay Status",
        description=f"Configured by {user_data.get('username', interaction.user.display_name)}",
        colour=discord.Colour.green(),
    )

    for game, data in user_data["games"].items():
        source_id = data.get("source")
        destinations = data.get("destinations", [])
        value = f"📥 Source: <#{source_id}>\n" if source_id else "📥 Source: ❌ Not set\n"

        if destinations:
            value += "📤 Destinations:\n"
            value += "\n".join(f"└ <#{destination_id}>" for destination_id in destinations)
        else:
            value += "📤 Destinations: ❌ None set"

        icon = "✅" if source_id and destinations else "⚠️"
        embed.add_field(name=f"{icon} {game}", value=value[:1024], inline=False)

    await interaction.response.send_message(embed=embed)


@client.event
async def on_ready():
    synced = await client.tree.sync()
    logger.info("=" * 40)
    logger.info("Logged in as %s", client.user)
    logger.info("Synced %s global commands", len(synced))
    logger.info("=" * 40)


@client.event
async def on_message(message: discord.Message):
    # Ignore only this bot. Followed announcement messages can be authored by bots,
    # and must still be relayed.
    if client.user and message.author.id == client.user.id:
        return
    if message.guild is None or message.id in forwarded_messages:
        return

    game = None
    destinations = []
    database = get_database()

    for user_data in database.values():
        for name, relay in user_data.get("games", {}).items():
            if message.channel.id == relay.get("source"):
                game = name
                destinations = relay.get("destinations", [])
                break
        if game:
            break

    if not game:
        return
    if not destinations:
        logger.warning("%s has no destinations set yet", game)
        return

    files = [await attachment.to_file() for attachment in message.attachments]
    forwarded_count = 0

    for destination_id in destinations:
        try:
            destination = client.get_channel(destination_id)
            if destination is None:
                destination = await client.fetch_channel(destination_id)

            await destination.send(
                content=f"## 📰 {game} Update\n\n{message.content}",
                embeds=message.embeds,
                files=files if forwarded_count == 0 else [
                    await attachment.to_file() for attachment in message.attachments
                ],
                allowed_mentions=discord.AllowedMentions.none(),
            )
            forwarded_count += 1
        except (discord.Forbidden, discord.HTTPException, discord.NotFound) as error:
            logger.error(
                "Could not forward %s update to destination %s: %s",
                game,
                destination_id,
                error,
            )

    if forwarded_count:
        forwarded_messages.add(message.id)
        save_forwarded_messages(forwarded_messages)
        logger.info("Forwarded %s update to %s destination(s)", game, forwarded_count)


@client.tree.error
async def on_app_command_error(interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        message = "❌ You need the **Manage Server** permission to use this command."
    else:
        logger.exception("Application command failed", exc_info=error)
        message = "❌ Something went wrong while running that command."

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from the .env file.")

client.run(TOKEN)
