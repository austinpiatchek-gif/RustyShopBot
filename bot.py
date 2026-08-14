import os
import re
import aiohttp
import discord

from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from urllib.parse import urljoin


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
# HTTP HEADERS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36"
    )
}


# ============================================================
# GET RUST SHOP PAGE
# ============================================================

async def get_store_page():

    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(
        timeout=timeout,
        headers=HEADERS
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

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


# ============================================================
# FIND CURRENT SHOP DATE
# ============================================================

def find_shop_date(soup):

    text = soup.get_text(
        " ",
        strip=True
    )

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

    text = clean_text(
        card.get_text(
            " ",
            strip=True
        )
    )

    prices = re.findall(
        r"\$(\d+\.\d{2})",
        text
    )

    if not prices:
        return None

    return float(prices[0])


# ============================================================
# NORMALIZE URL
# ============================================================

def normalize_url(
    url,
    base_url=None
):

    if not url:
        return None

    url = url.strip()

    if url.startswith("data:"):
        return None

    if url.startswith("//"):
        return "https:" + url

    if base_url:
        return urljoin(
            base_url,
            url
        )

    return url


# ============================================================
# FIND IMAGE IN HTML
# ============================================================

def find_image_in_html(
    soup,
    base_url=None
):

    # --------------------------------------------------------
    # OpenGraph
    # --------------------------------------------------------

    image = soup.find(
        "meta",
        property="og:image"
    )

    if image:

        content = image.get("content")

        if content:

            return normalize_url(
                content,
                base_url
            )

    # --------------------------------------------------------
    # Twitter
    # --------------------------------------------------------

    image = soup.find(
        "meta",
        attrs={
            "name": "twitter:image"
        }
    )

    if image:

        content = image.get("content")

        if content:

            return normalize_url(
                content,
                base_url
            )

    # --------------------------------------------------------
    # Normal images
    # --------------------------------------------------------

    for image in soup.find_all("img"):

        possible_urls = [

            image.get("src"),

            image.get("data-src"),

            image.get("data-lazy-src"),

            image.get("data-original"),

            image.get("data-image"),

            image.get("data-url"),

        ]

        for possible_url in possible_urls:

            normalized = normalize_url(
                possible_url,
                base_url
            )

            if normalized:

                return normalized

    return None


# ============================================================
# GET ITEM IMAGE
# ============================================================

async def get_item_image(
    session,
    item_url
):

    if not item_url:
        return None

    try:

        print(
            f"Getting image from item page: {item_url}"
        )

        async with session.get(
            item_url,
            timeout=15
        ) as response:

            if response.status != 200:

                print(
                    f"Image page returned HTTP "
                    f"{response.status}"
                )

                return None

            html = await response.text()

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        image_url = find_image_in_html(
            soup,
            item_url
        )

        if image_url:

            print(
                f"Image found: {image_url}"
            )

            return image_url

    except Exception as e:

        print(
            f"Could not get image for "
            f"{item_url}: {e}"
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

    headings = soup.find_all("h3")

    # --------------------------------------------------------
    # These are NOT shop items.
    # --------------------------------------------------------

    ignored_names = {
        "latest",
        "usd",
        "rust item store",
        "visit the rust wiki",
    }

    for heading in headings:

        name = clean_text(
            heading.get_text(
                " ",
                strip=True
            )
        )

        if not name:
            continue

        # ----------------------------------------------------
        # IGNORE NON-ITEM HEADINGS
        # ----------------------------------------------------

        if name.lower() in ignored_names:

            print(
                f"Ignoring non-item heading: {name}"
            )

            continue

        # ----------------------------------------------------
        # FIND ITEM CARD
        # ----------------------------------------------------

        card = heading

        for _ in range(6):

            if card.parent is None:
                break

            card = card.parent

            card_text = clean_text(
                card.get_text(
                    " ",
                    strip=True
                )
            )

            if re.search(
                r"\$\d+\.\d{2}",
                card_text
            ):

                break

        price = find_price(
            card
        )

        if price is None:
            continue

        # ----------------------------------------------------
        # FIND ITEM URL
        # ----------------------------------------------------

        link = None

        heading_link = heading.find("a")

        if heading_link:

            link = heading_link.get(
                "href"
            )

        if not link:

            card_link = card.find("a")

            if card_link:

                link = card_link.get(
                    "href"
                )

        link = normalize_url(
            link,
            "https://rusthelp.com"
        )

        # ----------------------------------------------------
        # FIND IMAGE DIRECTLY FROM CARD
        # ----------------------------------------------------

        image_url = None

        image = card.find("img")

        if image:

            possible_images = [

                image.get("src"),

                image.get("data-src"),

                image.get("data-lazy-src"),

                image.get("data-original"),

                image.get("data-image"),

                image.get("data-url"),

            ]

            for possible_image in possible_images:

                normalized = normalize_url(
                    possible_image,
                    STORE_URL
                )

                if normalized:

                    image_url = normalized

                    break

        # ----------------------------------------------------
        # CHECK SRCSET
        # ----------------------------------------------------

        if not image_url and image:

            srcset = image.get(
                "srcset"
            )

            if srcset:

                first_image = (
                    srcset
                    .split(",")[0]
                    .strip()
                    .split(" ")[0]
                )

                image_url = normalize_url(
                    first_image,
                    STORE_URL
                )

        # ----------------------------------------------------
        # AVOID DUPLICATES
        # ----------------------------------------------------

        if any(
            item["name"].lower()
            == name.lower()
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

    return items


# ============================================================
# FILL IN MISSING IMAGES
# ============================================================

async def add_missing_images(items):

    timeout = aiohttp.ClientTimeout(
        total=30
    )

    async with aiohttp.ClientSession(
        timeout=timeout,
        headers=HEADERS
    ) as session:

        for item in items:

            if item.get("image"):

                print(
                    f"Image already found for "
                    f"{item['name']}"
                )

                continue

            print(
                f"No image found on shop card for "
                f"{item['name']}"
            )

            if not item.get("url"):

                print(
                    f"No item URL available for "
                    f"{item['name']}"
                )

                continue

            image_url = await get_item_image(
                session,
                item["url"]
            )

            if image_url:

                item["image"] = image_url

            else:

                print(
                    f"❌ IMAGE NOT FOUND: "
                    f"{item['name']}"
                )

    return items


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

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    embed = discord.Embed(
        title=(
            f"🛒 RUST ITEM SHOP — "
            f"{date_text}"
        ),
        description=(
            "🔥 **New weekly Rust Item Shop!**\n\n"
            f"**{len(items)} items available**"
        ),
        color=0xE67E22
    )

    embed.set_footer(
        text=(
            "RustyShopBot • "
            "Weekly Rust Item Shop"
        )
    )

    await channel.send(
        embed=embed
    )

    # --------------------------------------------------------
    # ITEMS
    # --------------------------------------------------------

    for item in items:

        price_text = format_price(
            item["price"]
        )

        item_embed = discord.Embed(
            title=(
                f"{item['name']} — "
                f"{price_text}"
            ),
            color=0xE67E22
        )

        # Clickable item link
        if item.get("url"):

            item_embed.url = item["url"]

        # Item image
        if item.get("image"):

            print(
                f"Posting image for "
                f"{item['name']}: "
                f"{item['image']}"
            )

            item_embed.set_image(
                url=item["image"]
            )

        else:

            print(
                f"⚠️ NO IMAGE FOR "
                f"{item['name']}"
            )

            item_embed.description = (
                "⚠️ Image unavailable"
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
                "Could not find the Rust shop "
                "start date."
            )

        print(
            f"RustHelp shop date: {shop_date}"
        )

        # ----------------------------------------------------
        # SAFETY CHECK
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

        # ----------------------------------------------------
        # IMPORTANT: MUST FIND ALL 10
        # ----------------------------------------------------

        if len(items) != 10:

            print(
                "SHOP ITEMS FOUND:"
            )

            for item in items:

                print(
                    f"- {item['name']}"
                )

            raise RuntimeError(
                f"Expected 10 shop items, "
                f"but only found {len(items)}. "
                "Nothing will be posted."
            )

        print(
            f"Found exactly {len(items)} "
            f"shop items."
        )

        # ----------------------------------------------------
        # FIND MISSING IMAGES
        # ----------------------------------------------------

        print(
            "Checking item images..."
        )

        items = await add_missing_images(
            items
        )

        # ----------------------------------------------------
        # PRINT FINAL SHOP
        # ----------------------------------------------------

        print(
            "FINAL SHOP:"
        )

        for item in items:

            image_status = (
                "IMAGE FOUND"
                if item.get("image")
                else "NO IMAGE"
            )

            print(
                f"{item['name']} "
                f"-> "
                f"{format_price(item['price'])} "
                f"-> "
                f"{image_status}"
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


# ============================================================
# START BOT
# ============================================================

client.run(TOKEN)
