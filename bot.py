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
        async with session.get(
            API_URL,
            timeout=30,
            headers={"User-Agent": "RustyShopBot/1.0"}
        ) as response:

            response.raise_for_status()
            return await response.json()


def find_weekly_store(data):
    """
    SCMM can return the current store as either a store object
    or a wrapper containing the store object.
    """

    if isinstance(data, dict):

        # If the response itself is the store
        if any(
            key in data
            for key in (
                "items",
                "storeItems",
                "itemStoreItems",
                "storeItems"
            )
        ):
            return data

        # Common wrapper fields
        for key in (
            "data",
            "store",
            "current",
            "result"
        ):
            value = data.get(key)

            if isinstance(value, dict):
                return value

    return data


def get_items(store):
    if isinstance(store, list):
        return store

    if not isinstance(store, dict):
        return []

    # Look for the actual store item collection.
    for key in (
        "items",
        "storeItems",
        "itemStoreItems",
        "storeItemInstances"
    ):

        value = store.get(key)

        if isinstance(value, list):
            return value

    # Some API responses may nest the items.
    for key in (
        "data",
        "store",
        "current"
    ):

        value = store.get(key)

        if isinstance(value, dict):

            for item_key in (
                "items",
                "storeItems",
                "itemStoreItems"
            ):

                items = value.get(item_key)

                if isinstance(items, list):
                    return items

    return []


def get_name(item):

    return (
        item.get("name")
        or item.get("displayName")
        or item.get("itemName")
        or item.get("title")
        or "Unknown Skin"
    )


def get_store_price(item):

    # IMPORTANT:
    # Prefer the Rust Store price over market prices.

    possible_prices = (
        "storePrice",
        "price",
        "store_price",
        "priceUsd",
        "priceUSD",
        "usdPrice",
        "cost"
    )

    for key in possible_prices:

        value = item.get(key)

        if value is None:
            continue

        # Sometimes the API returns a nested price object.
        if isinstance(value, dict):

            for nested_key in (
                "amount",
                "value",
                "usd",
                "price"
            ):

                nested = value.get(nested_key)

                if nested is not None:

                    try:
                        return f"${float(nested):.2f}"
                    except:
                        return str(nested)

        try:
            return f"${float(value):.2f}"
        except:
            return str(value)

    return "Price unavailable"


def get_image(item):

    possible_images = (
        "imageUrl",
        "imageURL",
        "image",
        "iconUrl",
        "iconURL",
        "thumbnailUrl",
        "thumbnail",
        "icon"
    )

    for key in possible_images:

        value = item.get(key)

        if isinstance(value, str) and value.startswith("http"):
            return value

    return None


def is_weekly_item(item):

    """
    Filter out obvious permanent-store entries.
    """

    if not isinstance(item, dict):
        return True

    # If SCMM explicitly marks something permanent,
    # don't include it in the weekly shop.
    permanent = item.get("permanent")

    if permanent is True:
        return False

    item_type = str(
        item.get("type")
        or item.get("storeType")
        or ""
    ).lower()

    if "permanent" in item_type:
        return False

    return True


async def post_shop():

    channel = client.get_channel(CHANNEL_ID)

    if channel is None:

        print(
            "ERROR: Could not find channel "
            f"{CHANNEL_ID}"
        )

        return

    data = await get_store()

    store = find_weekly_store(data)

    items = get_items(store)

    if not items:

        print("ERROR: No Rust shop items were found.")
        print("API response:")
        print(data)

        return

    # Remove permanent-store items when possible.
    weekly_items = [
        item
        for item in items
        if is_weekly_item(item)
    ]

    # If filtering removed everything, use the returned list.
    if not weekly_items:
        weekly_items = items

    today = datetime.now(
        ZoneInfo("America/Chicago")
    )

    # ==========================
    # HEADER
    # ==========================

    header = discord.Embed(
        title=(
            "🛒 RUST ITEM SHOP — "
            f"{today.strftime('%B %d, %Y').upper()}"
        ),
        description="This week's Rust Item Shop",
    )

    embeds = [header]

    # ==========================
    # ITEMS
    # ==========================

    for item in weekly_items:

        name = get_name(item)
        price = get_store_price(item)
        image = get_image(item)

        embed = discord.Embed(
            title=f"{name} — {price}"
        )

        if image:
            embed.set_image(url=image)

        embeds.append(embed)

        print(
            f"SHOP ITEM: {name} | {price}"
        )

    # ==========================
    # DISCORD LIMIT
    # ==========================

    # Discord allows a maximum of
    # 10 embeds per message.

    for start in range(
        0,
        len(embeds),
        10
    ):

        chunk = embeds[start:start + 10]

        await channel.send(
            embeds=chunk
        )

    print(
        f"SUCCESS: Posted {len(weekly_items)} "
        "Rust shop items."
    )


@client.event
async def on_ready():

    print(
        f"Logged in as {client.user}"
    )

    print(
        "RustyShopBot is running."
    )

    try:

        await post_shop()

    except Exception as error:

        print(
            "ERROR:"
        )

        print(error)

    finally:

        await client.close()


client.run(TOKEN)
