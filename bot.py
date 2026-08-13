import os
import asyncio
import aiohttp
import discord
from discord.ext import tasks
from datetime import datetime
from zoneinfo import ZoneInfo

# ==============================
# SETTINGS
# ==============================

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]

CHANNEL_ID = 1537599173208309790

SCMM_API = "https://sbox.scmm.app/api/store/current"

CHECK_EVERY_MINUTES = 10

# Houston / Central Time
TIMEZONE = ZoneInfo("America/Chicago")

# ==============================
# DISCORD SETUP
# ==============================

intents = discord.Intents.default()

bot = discord.Client(intents=intents)


# ==============================
# GET RUST STORE
# ==============================

async def get_rust_store():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(SCMM_API, timeout=30) as response:

                if response.status != 200:
                    print(f"SCMM API returned HTTP {response.status}")
                    return None

                return await response.json()

    except Exception as e:
        print(f"Error getting Rust store: {e}")
        return None


# ==============================
# EXTRACT ITEMS
# ==============================

def extract_items(store_data):

    # SCMM's API can change its response structure,
    # so we look for common item-list fields.

    if not isinstance(store_data, dict):
        return []

    possible_lists = [
        store_data.get("items"),
        store_data.get("storeItems"),
        store_data.get("itemStoreItems"),
    ]

    for items in possible_lists:
        if isinstance(items, list):
            return items

    return []


def get_item_name(item):

    return (
        item.get("name")
        or item.get("itemName")
        or item.get("displayName")
        or "Unknown Rust Item"
    )


def get_item_price(item):

    price = (
        item.get("price")
        or item.get("storePrice")
        or item.get("priceUsd")
    )

    if price is None:
        return "Price unavailable"

    try:
        return f"${float(price):.2f}"
    except:
        return str(price)


def get_item_image(item):

    return (
        item.get("imageUrl")
        or item.get("image")
        or item.get("iconUrl")
        or item.get("thumbnailUrl")
        or item.get("icon")
    )


# ==============================
# CREATE DISCORD MESSAGE
# ==============================

async def create_shop_message(store_data):

    items = extract_items(store_data)

    if not items:
        print("No store items found.")
        return None

    now = datetime.now(TIMEZONE)

    title = f"🛒 RUST ITEM SHOP — {now.strftime('%B %d, %Y').upper()}"

    embeds = []

    # One embed for the title
    header = discord.Embed(
        title=title,
        description="This week's Rust Item Shop is here!",
    )

    embeds.append(header)

    for item in items:

        name = get_item_name(item)
        price = get_item_price(item)
        image = get_item_image(item)

        embed = discord.Embed(
            title=f"{name} — {price}"
        )

        if image and isinstance(image, str):
            embed.set_image(url=image)

        embeds.append(embed)

    return embeds


# ==============================
# SEND SHOP
# ==============================

async def send_shop():

    channel = bot.get_channel(CHANNEL_ID)

    if channel is None:
        print("Could not find #rust-shop.")
        return

    store = await get_rust_store()

    if store is None:
        return

    embeds = await create_shop_message(store)

    if not embeds:
        return

    # Discord allows a maximum of 10 embeds per message.
    # Therefore we send the shop in chunks while keeping
    # the weekly shop together.

    for i in range(0, len(embeds), 10):

        chunk = embeds[i:i + 10]

        await channel.send(
            embeds=chunk
        )

        await asyncio.sleep(1)

    print("Rust Item Shop posted successfully.")


# ==============================
# CHECK FOR NEW SHOP
# ==============================

last_store_id = None


@tasks.loop(minutes=CHECK_EVERY_MINUTES)
async def check_store():

    global last_store_id

    store = await get_rust_store()

    if not store:
        return

    store_id = (
        store.get("id")
        or store.get("storeId")
        or store.get("date")
        or store.get("releaseDate")
    )

    if store_id is None:
        print("Could not determine store ID.")
        return

    if last_store_id is None:

        # First run:
        # remember the current shop without posting it.
        last_store_id = store_id

        print(f"Current Rust shop detected: {store_id}")
        print("Waiting for the next shop update.")

        return

    if store_id != last_store_id:

        print("NEW RUST ITEM SHOP DETECTED!")

        last_store_id = store_id

        await send_shop()


# ==============================
# BOT STARTUP
# ==============================

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")
    print("RustyShopBot is online!")

    if not check_store.is_running():
        check_store.start()


bot.run(DISCORD_TOKEN)
