import os
import re
import aiohttp
import discord

from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup


# ============================================================
# SETTINGS
# ============================================================

TOKEN = os.environ["DISCORD_TOKEN"]

CHANNEL_ID = 1537599173208309790

STORE_URL = "https://rusthelp.com/store"

TIMEZONE = ZoneInfo("America/Chicago")


# ============================================================
# DISCORD
# ============================================================

intents = discord.Intents.default()

client = discord.Client(intents=intents)


# ============================================================
# GET RUST SHOP PAGE
# ============================================================

async def get_store_page():

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/151.0 Safari/537.36"
        )
    }

    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(
        timeout=timeout,
        headers=headers
    ) as session:

        async with session.get(STORE_URL) as response:

            response.raise_for_status()

            return await response.text()


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):

    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip()


# ============================================================
# FIND CURRENT SHOP DATE
# ============================================================

def find_shop_date(soup):

    text = soup.get_text(" ", strip=True)

    match = re.search(
        r"Started on\s+(\d{2}/\d{2}/\d{4})",
        text,
        re.IGNORECASE
    )

    if not match:
        return None

    try:

        return datetime.strptime(
            match.group(1),
            "%m/%d/%Y"
        ).date()

    except ValueError:

        return None


# ============================================================
# PRICE
# ============================================================

def find_price(card):

    text = clean_text(card.get_text(" ", strip=True))

    # Find prices such as:
    # $1.49
    # $2.99
    # $3.99

    prices = re.findall(
        r"\$(\d+\.\d{2})",
        text
    )

    if not prices:
        return None

    # The first price is the Rust Store price.
    return float(prices[0])


# ============================================================
# IMAGE
# ============================================================

async def get_item_image(session, item_url):

    if not item_url:
        return None

    try:

        async with session.get(
            item_url,
            timeout=15
        ) as response:

            if response.status != 200:
                return None

            html = await response.text()

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        # Try OpenGraph image first.
        image = soup.find(
            "meta",
            property="og:image"
        )

        if image and image.get("content"):
            return image["content"]

        # Try Twitter image.
        image = soup.find(
            "meta",
            attrs={"name": "twitter:image"}
        )

        if image and image.get("content"):
            return image["content"]

        # Try normal images.
        image = soup.find("img")

        if image and image.get("src"):
            return image["src"]

    except Exception as e:

        print(
            f"Could not get image for {item_url}: {e}"
        )

    return None


# ============================================================
# FIND SHOP ITEMS
# ============================================================

async def find_items(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    items = []

    # RustHelp currently displays each store item
    # as an H3 heading.
    headings = soup.find_all("h3")

    for heading in headings:

        name = clean_text(
            heading.get_text(" ", strip=True)
        )

        if not name:
            continue

        # Ignore headings that obviously aren't store items.
        if name.lower() in {
            "latest",
            "usd",
            "rust item store"
        }:
            continue

        # Walk upward until we find a useful card/container.
        card = heading

        for _ in range(6):

            if card.parent is None:
                break

            card = card.parent

            card_text = clean_text(
                card.get_text(" ", strip=True)
            )

            # A store item card should contain a dollar price.
            if re.search(
                r"\$\d+\.\d{2}",
                card_text
            ):

                break

        price = find_price(card)

        if price is None:
            continue

        # Try to find the item's RustHelp URL.
        link = None

        # First check the heading itself.
        heading_link = heading.find("a")

        if heading_link and heading_link.get("href"):
            link = heading_link["href"]

        # Otherwise search the card.
        if not link:

            card_link = card.find("a")

            if card_link and card_link.get("href"):
                link = card_link["href"]

        if link:

            if link.startswith("/"):
                link = "https://rusthelp.com" + link

            elif link.startswith("//"):
                link = "https:" + link

        # Try image directly from the card first.
        image_url = None

        image = card.find("img")

        if image:

            image_url = (
                image.get("src")
                or image.get("data-src")
                or image.get("data-lazy-src")
            )

        if image_url and image_url.startswith("//"):
            image_url = "https:" + image_url

        # Avoid duplicate items.
        if any(
            item["name"].lower() == name.lower()
            for item in items
        ):
            continue

        items.append(
            {
                "name": name,
                "price": price,
                "url": link,
                "image": image_url,
            }
        )

    # Keep only actual store items.
    # The current weekly Rust store has 10 items.
    return items[:10]


# ============================================================
# FORMAT PRICE
# ============================================================

def format_price(price):

    return f"${price:.2f}"


# ============================================================
# POST SHOP
# ============================================================

async def post_shop(
    channel,
    shop_date,
    items
):

    date_text = shop_date.strftime(
        "%B %d, %Y"
    )

    embed = discord.Embed(
        title=f"🛒 RUST ITEM SHOP — {date_text}",
        description=(
            "🔥 **New weekly Rust Item Shop!**\n\n"
            f"**{len(items)} items available**"
        ),
        color=0xE67E22
    )

    embed.set_footer(
        text="RustyShopBot • Weekly Rust Item Shop"
    )

    await channel.send(
        embed=embed
    )

    # Post each item individually.
    # This keeps the name/price together with the image.
    for item in items:

        price_text = format_price(
            item["price"]
        )

        item_embed = discord.Embed(
            title=f"{item['name']} — {price_text}",
            color=0xE67E22
        )

        if item.get("url"):

            item_embed.url = item["url"]

        if item.get("image"):

            item_embed.set_image(
                url=item["image"]
            )

        await channel.send(
            embed=item_embed
        )


# ============================================================
# MAIN
# ============================================================

@client.event
async def on_ready():

    print(
        f"Logged in as {client.user}"
    )

    try:

        now = datetime.now(
            TIMEZONE
        )

        print(
            f"Current Central time: {now}"
        )

        # ----------------------------------------------------
        # ONLY RUN ON THURSDAY
        # ----------------------------------------------------

        if now.weekday() != 3:

            print(
                "Today is not Thursday. "
                "Nothing to do."
            )

            await client.close()

            return

        # ----------------------------------------------------
        # GET SHOP
        # ----------------------------------------------------

        print(
            "Downloading current Rust shop..."
        )

        html = await get_store_page()

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        shop_date = find_shop_date(
            soup
        )

        if not shop_date:

            raise RuntimeError(
                "Could not find the Rust shop start date."
            )

        print(
            f"RustHelp shop date: {shop_date}"
        )

        # ----------------------------------------------------
        # IMPORTANT SAFETY CHECK
        # ----------------------------------------------------
        # We only post today's Thursday shop.
        #
        # This prevents the bot from accidentally posting
        # an old July/August rotation again.
        # ----------------------------------------------------

        if shop_date != now.date():

            raise RuntimeError(
                "SAFETY CHECK FAILED!\n"
                f"Today's date: {now.date()}\n"
                f"Shop date: {shop_date}\n\n"
                "The shop source has not updated yet, "
                "so the bot will NOT post anything."
            )

        # ----------------------------------------------------
        # FIND ITEMS
        # ----------------------------------------------------

        print(
            "Finding shop items..."
        )

        items = await find_items(
            html
        )

        if not items:

            raise RuntimeError(
                "No shop items were found."
            )

        print(
            f"Found {len(items)} shop items."
        )

        for item in items:

            print(
                f"{item['name']} "
                f"-> "
                f"{format_price(item['price'])}"
            )

        # ----------------------------------------------------
        # DISCORD CHANNEL
        # ----------------------------------------------------

        channel = client.get_channel(
            CHANNEL_ID
        )

        if channel is None:

            channel = await client.fetch_channel(
                CHANNEL_ID
            )

        # ----------------------------------------------------
        # POST
        # ----------------------------------------------------

        print(
            "Posting shop to Discord..."
        )

        await post_shop(
            channel,
            shop_date,
            items
        )

        print(
            "SHOP POSTED SUCCESSFULLY!"
        )

    except Exception as e:

        print(
            "ERROR:"
        )

        print(e)

        raise

    finally:

        await client.close()


client.run(TOKEN)
