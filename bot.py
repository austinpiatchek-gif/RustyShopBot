import os
import aiohttp
import discord
from datetime import datetime
from zoneinfo import ZoneInfo

TOKEN = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = 1537599173208309790

API_URL = "https://rust.scmm.app/api/store/current"

intents = discord.Intents.default()
client = discord.Client(intents=intents)


async def get_store():
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL) as response:
            response.raise_for_status()
            return await response.json()


def find_items(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["items", "storeItems", "itemStoreItems", "results"]:
            value = data.get(key)
            if isinstance(value, list):
                return value

    return []


def get_value(item, *names):
    for name in names:
        value = item.get(name)
        if value is not None:
            return value
    return None


async def post_shop():
    channel = client.get_channel(CHANNEL_ID)

    if channel is None:
        print("ERROR: Could not find #rust-shop.")
        return

    data = await get_store()
    items = find_items(data)

    if not items:
        print("ERROR: No Rust store items were found.")
        print(data)
        return

    today = datetime.now(ZoneInfo("America/Chicago"))

    header = discord.Embed(
        title=f"🛒 RUST ITEM SHOP — {today.strftime('%B %d, %Y').upper()}",
        description="This week's Rust Item Shop",
    )

    embeds = [header]

    for item in items:
        name = get_value(
            item,
            "name",
            "itemName",
            "displayName",
            "title"
        ) or "Unknown Item"

        price = get_value(
            item,
            "price",
            "storePrice",
            "priceUsd",
            "priceUSD"
        )

        image = get_value(
            item,
            "imageUrl",
            "image",
            "iconUrl",
            "thumbnailUrl",
            "icon"
        )

        if price is not None:
            try:
                price_text = f"${float(price):.2f}"
            except (ValueError, TypeError):
                price_text = str(price)
        else:
            price_text = "Price unavailable"

        embed = discord.Embed(
            title=f"{name} — {price_text}"
        )

        if image:
            embed.set_image(url=str(image))

        embeds.append(embed)

    # Discord allows up to 10 embeds in one message.
    for start in range(0, len(embeds), 10):
        await channel.send(
            embeds=embeds[start:start + 10]
        )

    print("Rust Item Shop posted successfully.")


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

    try:
        await post_shop()
    finally:
        await client.close()


client.run(TOKEN)
