"""Long-form, genuinely useful category copy for the shop pages.

Each entry gives a category page its own title, H1, meta description and
introductory copy so pages like ``/category/candle-molds/`` are useful in
their own right instead of being thin keyword shells.

Rules honoured here:
* content helps a candle maker choose the right material;
* it never claims "best in Nepal", awards, ratings or customer counts;
* it never repeats the target phrase unnaturally;
* it only references products/services the shop actually offers.

Keys are normalised slugs (lowercase, non-alphanumerics collapsed to "-"),
so ``/category/Silicone-Mould/`` and ``/category/silicone-moulds/`` resolve
to the same copy.
"""
from __future__ import annotations

import re

from .seo import BRAND_NAME, BUSINESS_CITY, BUSINESS_COUNTRY

__all__ = ["normalize_slug", "category_seo", "CATEGORY_CONTENT"]


def normalize_slug(slug: str) -> str:
    slug = (slug or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _lookup_keys(slug: str) -> list[str]:
    """Slug variants to try, so `candle-molds` and `candle-moulds` both hit.

    The catalogue is admin-editable and mixes the US and UK spellings
    ("Molds" / "Mould"); the SEO copy should not depend on which one an
    admin typed into the category name.
    """
    key = normalize_slug(slug)
    keys = [key]
    if "mould" in key:
        keys.append(key.replace("mould", "mold"))
    if "mold" in key:
        keys.append(key.replace("mold", "mould"))
    if key.endswith("s"):
        keys.append(key[:-1])
    else:
        keys.append(f"{key}s")
    return keys


# Factual, reusable copy fragments (no superlatives, no invented facts).
_SHIPPING_NOTE = (
    f"Orders placed on this page are packed and dispatched from {BUSINESS_CITY} "
    f"and delivered to customers across {BUSINESS_COUNTRY} through our "
    "courier partners."
)

# Curated, per-category copy. Keys are normalised slugs.
CATEGORY_CONTENT: dict[str, dict] = {}

CATEGORY_CONTENT["candle-moulds"] = {
    "seo_title": f"Candle Moulds in Nepal | {BRAND_NAME}",
    "h1": "Candle Moulds in Nepal",
    "meta_description": (
        "Shop silicone candle moulds in Nepal at Nismita Craft Studio. "
        "Choose the right shape, size and material for your wax, with "
        "delivery across Nepal from Kathmandu."
    ),
    "intro": (
        "<p>A candle mould decides the final shape, size and surface of a "
        "finished candle, so it is worth choosing carefully. At "
        f"{BRAND_NAME} we stock silicone candle moulds in a range of shapes "
        "and sizes, from single servings to larger jars and decorative "
        "designs, suitable for beginners and for makers producing in "
        "batches.</p>"
    ),
    "sections": [
        (
            "Why silicone moulds are the most forgiving choice",
            "<p>Silicone is flexible, heat resistant and does not stick, so a "
            "cooled candle releases with a gentle pull instead of being chipped "
            "out with a knife. That matters when you are pouring tapered "
            "shapes, deep designs or candles with sharp details: a rigid mould "
            "needs more tapping and more wax to release cleanly, and the risk "
            "of tearing the wick or denting the surface goes up with it.</p>"
            "<p>Silicone moulds also survive repeated use if you pour at the "
            "temperature the mould is rated for and let the wax cool fully "
            "before flexing it. Moulds used for pillars and tapers are usually "
            "thinner-walled than jar moulds, so pour those slightly cooler.</p>",
        ),
        (
            "How to choose a mould that suits your wax",
            "<p>Match the mould to the wax you actually pour. Soy and coconut "
            "blends shrink slightly as they cool, so leave the cavity a few "
            "millimetres under-full if you want a clean flat top, and leave "
            "room for a double wick in wide moulds. Beeswax and paraffin blends "
            "hold detail better and can be poured closer to the top of the "
            "cavity.</p>"
            "<p>Check the wall thickness too. Very thin walls give the fastest "
            "release, but wide candles cast in a thin-walled mould need more "
            "support while the wax is still soft, so a thicker mould is easier "
            "to carry once it has just set.</p>",
        ),
        (
            "Sizes, shapes and how many candles you get",
            "<p>Mould sizes are usually listed as the finished candle size "
            "rather than the cavity size, which is the number you actually care "
            "about. Small moulds (roughly 30-60 g of wax) suit sampling a "
            "scent or a colour before committing to a full batch. Medium sizes "
            "(80-150 g) are the everyday choice for gift candles. Large jars "
            "and pillar moulds (200 g and above) are better made in small "
            "batches so the surface stays even.</p>"
            "<p>Decorative moulds - florals, fruits, animals, geometric and "
            "seasonal shapes - use more wax per candle because the design adds "
            "surface area. If you are working to a budget, mix a few statement "
            "shapes with simple classics.</p>",
        ),
        (
            "Using, cleaning and storing silicone moulds",
            "<p>Warm the mould, dust it sparingly where you want definition, "
            "and pour at the temperature recommended for your wax. After the "
            "candle has fully cooled, flex the mould and peel the candle away "
            "from the edges first. Wash in warm soapy water, avoid the "
            "dishwasher, and store flat and out of direct sunlight so the "
            "silicone does not warp.</p>",
        ),
    ],
}

CATEGORY_CONTENT["silicone-moulds"] = {
    "seo_title": f"Silicone Candle Moulds in Nepal | {BRAND_NAME}",
    "h1": "Silicone Candle Moulds",
    "meta_description": (
        "Buy silicone candle moulds in Nepal from Nismita Craft Studio. "
        "Flexible, non-stick moulds in different shapes and sizes, delivered "
        "across Nepal from Kathmandu."
    ),
    "intro": (
        "<p>Silicone candle moulds bend rather than chip, which is why they are "
        "the most commonly used mould material for home and small studio "
        f"candle making. This page collects the silicone moulds currently "
        f"available at {BRAND_NAME}.</p>"
    ),
    "sections": [
        (
            "What makes a silicone mould useful",
            "<p>Flexible walls release a cooled candle with a light pull, the "
            "surface stays smooth and detailed, and the mould can be washed in "
            "warm soapy water and reused. Thin walls cool faster, so a poured "
            "candle sets sooner and is easier to unmould while the wax is "
            "still firm.</p>",
        ),
        (
            "Silicone or metal?",
            "<p>Metal moulds stay rigid, which suits very hot waxes and "
            "produces a hard, glossy surface, but they need more cooling time "
            "and usually more tapping to release. Silicone is the easier choice "
            "for detailed shapes, beginners and frequent small batches. If you "
            "pour pillars or tapers in volume, a rigid mould with a wick pin "
            "gives a straighter result.</p>",
        ),
    ],
}

CATEGORY_CONTENT["candle-mould"] = {
    "seo_title": f"Candle Moulds in Nepal | {BRAND_NAME}",
    "h1": "Candle Moulds",
    "meta_description": (
        "Candle moulds in Nepal from Nismita Craft Studio - silicone moulds "
        "in different shapes and sizes, with delivery across Nepal."
    ),
    "intro": (
        "<p>Candle moulds available at Nismita Craft Studio. Choose a shape and "
        "size that matches the wax you pour and the number of candles you want "
        "to make in one batch.</p>"
    ),
    "sections": [
        (
            "Choosing a mould",
            "<p>Silicone moulds release easiest and hold the most detail. "
            "Leave a few millimetres of space at the top for shrinkage and for "
            "a second wick in wide candles, and make sure the mould is rated "
            "for the pouring temperature of your wax.</p>",
        ),
    ],
}

CATEGORY_CONTENT["candle-wax"] = {
    "seo_title": f"Candle Wax in Nepal | {BRAND_NAME}",
    "h1": "Candle Wax in Nepal",
    "meta_description": (
        "Buy candle wax in Nepal from Nismita Craft Studio. Soy wax and other "
        "candle-making waxes for jars, pillars and tappers, delivered across "
        "Nepal from Kathmandu."
    ),
    "intro": (
        "<p>Wax is the largest component of a candle by weight and the "
        "ingredient that most changes how it burns. At "
        f"{BRAND_NAME} we supply candle wax to makers across {BUSINESS_COUNTRY}, "
        "and the wax listed here is chosen for clean burning, easy pouring and "
        "repeatable results.</p>"
    ),
    "sections": [
        (
            "Soy wax",
            "<p>Soy wax burns slower and cleaner than paraffin and gives a "
            "slower, more even melt pool, which suits container candles and "
            "strongly scented pours. It throws scent well once the melt pool "
            "covers the full surface. Expect a slightly shorter throw than "
            "paraffin on the first burn, which improves as the wick is trimmed "
            "and the candle is conditioned.</p>",
        ),
        (
            "Choosing a wick size for your wax",
            "<p>Wick size depends on the wax, the candle diameter and the "
            "fragrance load together, not on one factor alone. A wider candle "
            "needs a larger wick; a heavy fragrance load or a higher pour "
            "temperature usually calls for the next size up. If you are "
            "unsure, test on a small batch and adjust before ordering in "
            "volume - we are happy to advise on WhatsApp.</p>",
        ),
        (
            "Pouring and storing wax",
            "<p>Melt in a dedicated melting pot or double boiler with a "
            "controlled heat source, never directly on a flame, and do not "
            "overheat. Let the wax cool to the pouring temperature recommended "
            "for the wax type; pouring too hot fragrances the air and dulls "
            "the surface. Store in a sealed, dry container away from sunlight "
            "and heat, and re-melt gently rather than repeatedly heating to a "
            "high temperature.</p>",
        ),
    ],
}

CATEGORY_CONTENT["candle-wicks"] = {
    "seo_title": f"Candle Wicks in Nepal | {BRAND_NAME}",
    "h1": "Candle Wicks in Nepal",
    "meta_description": (
        "Buy candle wicks in Nepal from Nismita Craft Studio. Cotton and cored "
        "wicks for jars, pillars and tappers, delivered across Nepal."
    ),
    "intro": (
        "<p>The wick controls how fast a candle burns and how much melt pool it "
        "forms. A wrong size gives you a tall flame, a sooty rim or a candle "
        "that tunnels down the middle. This page lists the wicks currently "
        f"stocked at {BRAND_NAME}.</p>"
    ),
    "sections": [
        (
            "Cotton and cored wicks",
            "<p>Flat braided cotton wicks sit neatly in jars and containers and "
            "are easy to centre before the wax sets. Cored wicks are stiffer, "
            "which helps in deeper pours and keeps the wick upright while the "
            "wax is still warm - a common choice for pillars and tall "
            "candles.</p>",
        ),
        (
            "Sizing and trimming",
            "<p>Wicks are sized by diameter and by wax type, and a wick that is "
            "one size too large will push wax over the rim or create a tall, "
            "sooty flame; one size too small leaves wax behind the wick. Always "
            "trim the wick to about 6 mm before lighting and between burns. Let "
            "the first burn reach the full diameter of the melt pool, or the "
            "candle will tunnel later.</p>",
        ),
        (
            "Keeping a good melt pool",
            "<p>Trim the wick, keep it centred, and avoid burning in a draught "
            "or in a room with a strong fan. If a candle burns too hot, step "
            "down a wick size; if it burns too cool, step up one size before "
            "adding more fragrance.</p>",
        ),
    ],
}

CATEGORY_CONTENT["candle-wick"] = {
    "seo_title": f"Candle Wicks in Nepal | {BRAND_NAME}",
    "h1": "Candle Wicks",
    "meta_description": (
        "Candle wicks for jars, pillars and tappers in Nepal, supplied by "
        "Nismita Craft Studio with delivery across Nepal."
    ),
    "intro": (
        "<p>Cotton and cored candle wicks for container candles, pillars and "
        f"tapers, supplied by {BRAND_NAME} and delivered across "
        f"{BUSINESS_COUNTRY}.</p>"
    ),
    "sections": [
        (
            "Choosing a wick",
            "<p>Size the wick to the candle diameter and the wax you pour, and "
            "trim to about 6 mm before every burn. Testing a small batch first "
            "is the cheapest way to avoid a tunnel or a sooty rim.</p>",
        ),
    ],
}

CATEGORY_CONTENT["colours-glitters"] = {
    "seo_title": f"Mica Colours & Glitters in Nepal | {BRAND_NAME}",
    "h1": "Mica Colours & Glitters in Nepal",
    "meta_description": (
        "Mica colours, pearlescent pigments and glitters for candle making in "
        "Nepal, supplied by Nismita Craft Studio with delivery across Nepal "
        "from Kathmandu."
    ),
    "intro": (
        "<p>Colour is what makes a finished candle look considered. Mica "
        "colours and glitters at Nismita Craft Studio are chosen to suspend "
        "evenly in wax and to stay stable instead of sinking or clumping, so a "
        "small amount goes a long way.</p>"
    ),
    "sections": [
        (
            "Mica colours",
            "<p>Mica is a pearlescent pigment with a fine, mineral-like flake. "
            "Used on its own it gives a soft, pearly look; mixed into wax it "
            "creates a subtle shimmer that catches light without looking "
            "glittery. Use it sparingly - a small amount lifted on a spatula "
            "goes into the whole batch evenly, whereas pouring it in one spot "
            "gives streaks.</p>",
        ),
        (
            "Using mica safely",
            "<p>Add mica after the wax has melted and before fragrance, and stir "
            "thoroughly to break up clumps. Because mica is a fine powder, "
            "weigh it with a small scale rather than estimating, and avoid "
            "generating dust at the melting pot.</p>",
        ),
        (
            "Glitters and finishes",
            "<p>Fine craft glitter gives a sparkle that is visible at a "
            "distance, while larger glitters read clearly on an open surface "
            "such as a candle topper. Test glitter in a small melt first: heavy "
            "pieces can float or sink depending on density, and some coloured "
            "glitters will bleed into the wax over time. For a controlled "
            "finish, a candle topper or a mould with a texture gives more "
            "reliable results than glitter suspended in the wax.</p>",
        ),
    ],
}

CATEGORY_CONTENT["mica-colours"] = {
    "seo_title": f"Mica Colours in Nepal | {BRAND_NAME}",
    "h1": "Mica Colours in Nepal",
    "meta_description": (
        "Mica colour pigments for candle making in Nepal from Nismita Craft "
        "Studio, delivered across Nepal from Kathmandu."
    ),
    "intro": (
        f"<p>Mica colours add a soft pearlescent shimmer to candles and other "
        f"wax melts. Supplied by {BRAND_NAME} in {BUSINESS_CITY} and delivered "
        f"across {BUSINESS_COUNTRY}.</p>"
    ),
    "sections": [
        (
            "Using mica colours",
            "<p>Mix mica into fully melted wax, then stir until evenly dispersed "
            "before adding fragrance. Weigh colours rather than guessing; too "
            "much mica can mute the scent throw.</p>",
        ),
    ],
}

CATEGORY_CONTENT["glitters"] = {
    "seo_title": f"Candle Glitters in Nepal | {BRAND_NAME}",
    "h1": "Candle Glitters in Nepal",
    "meta_description": (
        "Glitters for candle making in Nepal from Nismita Craft Studio, with "
        "candle moulds, toppers and finishes, delivered across Nepal."
    ),
    "intro": (
        f"<p>Glitter finishes for candles and other wax melts, supplied by "
        f"{BRAND_NAME} and delivered across {BUSINESS_COUNTRY}.</p>"
    ),
    "sections": [
        (
            "Glitter and melt stability",
            "<p>Test any glitter in a small melt first. Larger or coloured "
            "pieces may float or sink, and some will bleed into the wax. A "
            "candle topper or a textured mould gives a reliable sparkle without "
            "the settling problem.</p>",
        ),
    ],
}

CATEGORY_CONTENT["candle-making-supplies"] = {
    "seo_title": f"Candle Making Supplies in Nepal | {BRAND_NAME}",
    "h1": "Candle Making Supplies in Nepal",
    "meta_description": (
        "Candle making supplies in Nepal - moulds, wax, wicks, colours, "
        "glitters and tools from Nismita Craft Studio in Kathmandu, delivered "
        "across Nepal."
    ),
    "intro": (
        "<p>Everything needed to start making candles at home or in a small "
        "studio: moulds, wax, wicks, colours, glitters and tools, supplied by "
        f"{BRAND_NAME} in {BUSINESS_CITY} and delivered across "
        f"{BUSINESS_COUNTRY}.</p>"
    ),
    "sections": [
        (
            "What a first batch needs",
            "<p>For a container candle, a mould or jar, a matching wick, a kg of "
            "wax and a colour are enough to start. Tools such as a digital "
            "scale and a heat gun make measuring and finishing faster, but they "
            "are not required to begin.</p>",
        ),
    ],
}

CATEGORY_CONTENT["tools"] = {
    "seo_title": f"Candle Making Tools & Equipment in Nepal | {BRAND_NAME}",
    "h1": "Candle Making Tools & Equipment",
    "meta_description": (
        "Digital scales, thermometers and heat guns for candle making, supplied "
        "by Nismita Craft Studio in Kathmandu with delivery across Nepal."
    ),
    "intro": (
        "<p>Tools and small equipment for candle making, supplied by "
        f"{BRAND_NAME} and delivered across {BUSINESS_COUNTRY}.</p>"
    ),
    "sections": [
        (
            "Why tools matter",
            "<p>A scale lets you measure wax, fragrance and colour consistently, "
            "a thermometer keeps the pour temperature honest, and controlled "
            "heat makes melting safer. Accurate measurement is the single "
            "biggest factor in a repeatable result.</p>",
        ),
    ],
}


def _fallback(name: str, product_count: int) -> dict:
    """Factual, category-specific copy built from the real category name.

    Guarantees every category page still has its own title, H1, meta
    description and intro paragraph (no two categories share the same text).
    """
    clean = (name or "Craft Supplies").strip()
    count = ""
    if product_count:
        count = (
            f" Browse the {product_count} "
            f"product{'' if product_count == 1 else 's'} available now."
        )
    return {
        "seo_title": f"{clean} in Nepal | {BRAND_NAME}",
        "h1": f"{clean} in Nepal",
        "meta_description": (
            f"{clean} for candle and craft making in Nepal, supplied by "
            f"{BRAND_NAME} in Kathmandu with delivery across Nepal."
        )[:157],
        "intro": (
            f"<p>{clean} available from {BRAND_NAME}, a candle-making supplies "
            f"business based in {BUSINESS_CITY}. Orders are packed in Kathmandu "
            f"and delivered to customers across {BUSINESS_COUNTRY}.{count}</p>"
        ),
        "sections": [
            (
                "Ordering and delivery",
                f"<p>Add the items you need to your cart and check out. We "
                f"dispatch confirmed orders from {BUSINESS_CITY} through our "
                f"courier partners to customers across {BUSINESS_COUNTRY}, and "
                "delivery time depends on your location and the courier "
                "partner.</p>",
            ),
        ],
    }


def category_seo(slug: str, name: str, product_count: int = 0) -> dict:
    """Return the SEO fields for a category page.

    Uses the curated copy when a slug matches, otherwise a factual
    category-specific fallback — so no category page is ever left without a
    unique title, H1 and meta description.
    """
    keys = _lookup_keys(slug)
    entry = next((CATEGORY_CONTENT[k] for k in keys if k in CATEGORY_CONTENT), None)
    has_custom_copy = entry is not None
    if entry is None:
        entry = _fallback(name, product_count)
    return {
        "seo_title": entry["seo_title"],
        "h1": entry["h1"],
        "meta_description": entry["meta_description"],
        "intro_html": entry.get("intro", ""),
        "sections": entry.get("sections", []),
        "shipping_note": _SHIPPING_NOTE,
        "has_custom_copy": has_custom_copy,
    }