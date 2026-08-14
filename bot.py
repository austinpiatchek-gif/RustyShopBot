import os
import aiohttp
import discord
from datetime import datetime
from zoneinfo import ZoneInfo

TOKEN = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = 1537599173208309790

# CORRECT Rust SCMM API
API_URL = "https://rust.scmm.app/api/store/current"

intents = discord.Intents.default()
client = discord.Client(intents=intents)


async def get_store():
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL, timeout=30) as response:
            response.raise_for_status()
            return await response.json()


def find_items(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in (
            "items",
            "storeItems",
            "itemStoreItems",
            "results",
            "data",
        ):
            value = data.get(key)

            if isinstance(value, list):
                return value

            if isinstance(value, dict):
                for nested_key in ("items", "results", "data"):
                    nested = value.get(nested_key)
                    if isinstance(nested, list):
                        return nested

    return []


def get_name(item):
    return (
        item.get("name")
        or item.get("itemName")
        or item.get("displayName")
        or item.get("title")
        or "Unknown Item"
    )


def get_price(item):
    # Prefer the actual Rust Store price fields.
    price = (
        item.get("storePrice")
        or item.get("steamStorePrice")
        or item.get("price")
        or item.get("priceUsd")
        or item.get("priceUSD")
    )

    if price is None:
        return "Price unavailable"

    try:
        return f"${float(price):.2f}"
    except (ValueError, TypeError):
        return str(price)


def get_image(item):
    return (
        item.get("imageUrl")
        or item.get("image")
        or item.get("iconUrl")
        or item.get("thumbnailUrl")
        or item.get("icon")
    )


async def post_shop():

    channel = client.get_channel(CHANNEL_ID)

    if channel is None:
        print("ERROR: #rust-shop was not found.")
        return

    store = await get_store()

    print("Received Rust store data.")
    print(f"Data type: {type(store)}")

    items = find_items(store)

    if not items:
        print("ERROR: No shop items found.")
        print(store)
        return

    now = datetime.now(ZoneInfo("America/Chicago"))

    # Main title
    header = discord.Embed(
        title=f"🛒 RUST ITEM SHOP — {now.strftime('%B %d, %Y').upper()}",
        description="This week's Rust Item Shop",
    )

    embeds = [header]

    for item in items:

        name = get_name(item)
        price = get_price(item)
        image = get_image(item)

        embed = discord.Embed(
            title=f"{name} — {price}"
        )

        if image:
            embed.set_image(url=str(image))

        embeds.append(embed)

        print(f"Added: {name} | {price}")

    # Discord permits a maximum of 10 embeds per message.
    # We send chunks while keeping the shop update together.
    for start in range(0, len(embeds), 10):

        chunk = embeds[start:start + 10]

        await channel.send(embeds=chunk)

    print("SUCCESS: Rust Item Shop posted.")


@client.event
async def on_ready():

    print(f"Logged in as {client.user}")
    print("RustyShopBot is online.")

    try:
        await post_shop()
    except Exception as error:
        print(f"ERROR while posting shop: {error}")
    finally:
        await client.close()


client.run(TOKEN)
