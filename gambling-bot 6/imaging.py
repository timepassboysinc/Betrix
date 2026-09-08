"""
Generates the PNG cards sent alongside embeds (balance card, blackjack table).
Uses only Pillow + bundled default font so it works with zero extra assets.
Drop TTF files into an optional `fonts/` folder and point FONT_BOLD/FONT_REGULAR
at them for nicer typography — falls back cleanly if they're missing.
"""
import io
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont, ImageOps

FONT_BOLD = "fonts/Inter-Bold.ttf"
FONT_REGULAR = "fonts/Inter-Regular.ttf"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except (OSError, IOError):
        return ImageFont.load_default(size=size)


def _vertical_gradient(size, top_color, bottom_color):
    w, h = size
    base = Image.new("RGB", (1, h), color=0)
    draw = ImageDraw.Draw(base)
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        draw.point((0, y), fill=(r, g, b))
    return base.resize(size)


def _rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size[0], size[1]], radius=radius, fill=255)
    return mask


def _circle_avatar(avatar_bytes: bytes, diameter: int) -> Image.Image:
    img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    img = ImageOps.fit(img, (diameter, diameter))
    mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, diameter, diameter], fill=255)
    out = Image.new("RGBA", (diameter, diameter))
    out.paste(img, (0, 0), mask)
    return out


def _chip(diameter: int, label: str, ring_color=(230, 220, 200)) -> Image.Image:
    img = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, diameter, diameter], fill=(40, 40, 45, 255), outline=ring_color, width=4)
    d.ellipse([8, 8, diameter - 8, diameter - 8], outline=ring_color, width=2)
    f = _font(diameter // 4, bold=True)
    bbox = d.textbbox((0, 0), label, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((diameter - tw) / 2, (diameter - th) / 2 - bbox[1]), label, font=f, fill=ring_color)
    return img


def render_balance_card(username: str, user_id: int, avatar_bytes: bytes | None, balance: int) -> bytes:
    W, H = 900, 420
    card = _vertical_gradient((W, H), (18, 24, 46), (12, 14, 26)).convert("RGBA")
    draw = ImageDraw.Draw(card)

    # rounded card border effect
    mask = _rounded_mask((W, H), 28)
    rounded = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rounded.paste(card, (0, 0), mask)
    card = rounded
    draw = ImageDraw.Draw(card)

    # poker chips top-right
    chip1 = _chip(90, "100")
    chip2 = _chip(90, "1K")
    card.alpha_composite(chip1, (W - 210, 40))
    card.alpha_composite(chip2, (W - 110, 40))

    # avatar
    if avatar_bytes:
        avatar = _circle_avatar(avatar_bytes, 150)
        # ring
        ring = Image.new("RGBA", (166, 166), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse([0, 0, 166, 166], outline=(90, 140, 220, 255), width=4)
        card.alpha_composite(ring, (60, 70))
        card.alpha_composite(avatar, (68, 78))

    text_x = 260
    draw.text((text_x, 90), username, font=_font(46, bold=True), fill=(230, 230, 235))
    draw.text((text_x, 150), f"ID: {user_id}", font=_font(20), fill=(150, 150, 160))

    draw.text((text_x, 230), "POINTS BALANCE", font=_font(20, bold=True), fill=(150, 155, 170))
    draw.text((text_x, 255), f"{balance:,}", font=_font(64, bold=True), fill=(90, 140, 240))

    footer_y = H - 55
    draw.text((40, footer_y), "NeonVault Casino", font=_font(18), fill=(110, 115, 130))
    date_str = datetime.now(timezone.utc).strftime("%b %d, %Y, %I:%M %p UTC")
    bbox = draw.textbbox((0, 0), date_str, font=_font(18))
    draw.text((W - 40 - (bbox[2] - bbox[0]), footer_y), date_str, font=_font(18), fill=(110, 115, 130))

    buf = io.BytesIO()
    card.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def render_coinflip(result: str, won: bool | None) -> bytes:
    W = H = 260
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bg = _vertical_gradient((W, H), (30, 24, 55), (14, 12, 26)).convert("RGBA")
    mask = _rounded_mask((W, H), 24)
    rounded = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rounded.paste(bg, (0, 0), mask)
    img = rounded
    d = ImageDraw.Draw(img)

    cx, cy, r = W // 2, H // 2 - 10, 80
    face_color = (245, 200, 90) if result == "heads" else (200, 170, 230)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=face_color, outline=(30, 30, 35), width=6)
    d.ellipse([cx - r + 12, cy - r + 12, cx + r - 12, cy + r - 12], outline=(30, 30, 35), width=3)

    label = "H" if result == "heads" else "T"
    f = _font(64, bold=True)
    bbox = d.textbbox((0, 0), label, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((cx - tw / 2, cy - th / 2 - bbox[1]), label, font=f, fill=(30, 30, 35))

    f_small = _font(20, bold=True)
    caption = result.upper()
    bbox2 = d.textbbox((0, 0), caption, font=f_small)
    d.text(((W - (bbox2[2] - bbox2[0])) / 2, H - 40), caption, font=f_small, fill=(220, 220, 230))

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def render_dice_roll(roll: int) -> bytes:
    W = H = 220
    bg = _vertical_gradient((W, H), (24, 30, 55), (12, 14, 26)).convert("RGBA")
    mask = _rounded_mask((W, H), 24)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.paste(bg, (0, 0), mask)
    d = ImageDraw.Draw(img)

    die_size = 150
    x0, y0 = (W - die_size) // 2, (H - die_size) // 2
    d.rounded_rectangle([x0, y0, x0 + die_size, y0 + die_size], radius=20, fill=(250, 250, 248), outline=(20, 20, 25), width=5)

    f = _font(60, bold=True)
    text = str(roll)
    bbox = d.textbbox((0, 0), text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((W / 2 - tw / 2, H / 2 - th / 2 - bbox[1]), text, font=f, fill=(30, 30, 35))

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


SUIT_COLORS = {"♠": (30, 30, 35), "♣": (30, 30, 35), "♥": (200, 40, 50), "♦": (200, 40, 50)}


def _draw_suit_icon(d: ImageDraw.ImageDraw, suit: str, cx: float, cy: float, size: float, color):
    s = size
    if suit == "♦":
        d.polygon([(cx, cy - s), (cx + s * 0.62, cy), (cx, cy + s), (cx - s * 0.62, cy)], fill=color)
    elif suit == "♣":
        r = s * 0.42
        d.ellipse([cx - r, cy - s * 0.55 - r, cx + r, cy - s * 0.55 + r], fill=color)
        d.ellipse([cx - s * 0.5 - r, cy + s * 0.15 - r, cx - s * 0.5 + r, cy + s * 0.15 + r], fill=color)
        d.ellipse([cx + s * 0.5 - r, cy + s * 0.15 - r, cx + s * 0.5 + r, cy + s * 0.15 + r], fill=color)
        d.polygon(
            [(cx - s * 0.16, cy + s * 0.05), (cx + s * 0.16, cy + s * 0.05),
             (cx + s * 0.06, cy + s * 0.95), (cx - s * 0.06, cy + s * 0.95)],
            fill=color,
        )
    elif suit == "♥":
        r = s * 0.4
        d.ellipse([cx - 2 * r + r, cy - r * 0.9, cx + r, cy + r * 1.1], fill=color)
        d.ellipse([cx - r, cy - r * 0.9, cx + 2 * r - r, cy + r * 1.1], fill=color)
        d.polygon([(cx - 1.8 * r, cy + r * 0.3), (cx + 1.8 * r, cy + r * 0.3), (cx, cy + s)], fill=color)
    elif suit == "♠":
        r = s * 0.4
        d.ellipse([cx - 2 * r + r, cy - r * 1.1, cx + r, cy + r * 0.9], fill=color)
        d.ellipse([cx - r, cy - r * 1.1, cx + 2 * r - r, cy + r * 0.9], fill=color)
        d.polygon([(cx - 1.8 * r, cy + r * 0.5), (cx + 1.8 * r, cy + r * 0.5), (cx, cy - s * 0.8)], fill=color)
        d.polygon(
            [(cx - s * 0.14, cy + r * 0.55), (cx + s * 0.14, cy + r * 0.55),
             (cx + s * 0.05, cy + s * 0.95), (cx - s * 0.05, cy + s * 0.95)],
            fill=color,
        )


def _draw_card(draw_target: Image.Image, pos, card_str: str | None):
    """card_str like 'A♠' or '10♥'; None = face-down card back."""
    w, h = 90, 130
    x, y = pos
    card_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card_img)

    if card_str is None:
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=10, fill=(40, 60, 120), outline=(20, 30, 60), width=3)
        d.rounded_rectangle([10, 10, w - 11, h - 11], radius=6, outline=(80, 110, 200), width=3)
    else:
        rank, suit = card_str[:-1], card_str[-1]
        color = SUIT_COLORS.get(suit, (30, 30, 35))
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=10, fill=(250, 250, 248), outline=(20, 20, 25), width=3)
        f_rank = _font(24, bold=True)
        d.text((8, 6), rank, font=f_rank, fill=color)
        _draw_suit_icon(d, suit, 20, 40, 10, color)

        bbox_r = d.textbbox((0, 0), rank, font=f_rank)
        rw = bbox_r[2] - bbox_r[0]
        d.text((w - 8 - rw, h - 30), rank, font=f_rank, fill=color)
        _draw_suit_icon(d, suit, w - 20, h - 40, 10, color)

        _draw_suit_icon(d, suit, w / 2, h / 2, 22, color)

    draw_target.alpha_composite(card_img, (x, y))


def render_blackjack_table(player_cards: list[str], dealer_cards: list[str], hide_dealer_second: bool, player_val: int, dealer_val: str) -> bytes:
    card_w, gap = 90, 14
    row_w = max(len(player_cards), len(dealer_cards)) * (card_w + gap)
    W = max(600, row_w + 80)
    H = 380

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bg = _vertical_gradient((W, H), (10, 40, 20), (8, 20, 12)).convert("RGBA")
    mask = _rounded_mask((W, H), 24)
    rounded = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rounded.paste(bg, (0, 0), mask)
    img = rounded
    d = ImageDraw.Draw(img)

    f_label = _font(22, bold=True)
    d.text((40, 20), f"DEALER ({dealer_val})", font=f_label, fill=(230, 230, 235))
    x = 40
    for i, c in enumerate(dealer_cards):
        show_back = hide_dealer_second and i == 1
        _draw_card(img, (x, 50), None if show_back else c)
        x += card_w + gap

    d.text((40, 195), f"YOU ({player_val})", font=f_label, fill=(230, 230, 235))
    x = 40
    for c in player_cards:
        _draw_card(img, (x, 225), c)
        x += card_w + gap

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf.read()
