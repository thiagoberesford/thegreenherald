"""Central configuration for The Green Herald."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# --- Brand & identity ---
BRAND = "The Green Herald"
TAGLINE = "All the news that the planet can afford to print"
DOMAIN = "thegreenherald.com"
EDITION_URL_BASE = "https://" + DOMAIN
MASTHEAD_KICKER = "Your daily sustainability refresh"

# --- Sending ---
SENDER_NAME = BRAND
SENDER_EMAIL = "editor@" + DOMAIN               # branded sender (Resend, verified domain)
REPLY_TO = "reply@" + DOMAIN
UNSUBSCRIBE_TO = "unsubscribe@" + DOMAIN
# With RESEND_API_KEY set, sends via Resend SMTP. Without it, Gmail SMTP fallback.

# --- LLM ---
LLM_MODEL = "mistral-small-latest"
LLM_MAX_TOKENS = 8192

# --- Time windows ---
#   NEWS:   yesterday 00:00 Lisbon -> today 05:00 (closes 1h before the 06:00 edition)
#   EVENTS: today 05:00 Lisbon    -> end of the current quarter (+ optional lookahead)
TIMEZONE = "Europe/Lisbon"
LISBON_TZ = ZoneInfo(TIMEZONE)
SEND_HOUR_LOCAL = 6
WINDOW_CLOSES_BEFORE_SEND_H = 1
EVENT_LOOKAHEAD_QUARTERS = 0       # 0 = until end of current quarter; 1 = also next quarter


def get_time_windows(now: datetime | None = None) -> dict[str, datetime]:
    """Timezone-aware windows for news and events.

    Any run before 07:00 Lisbon belongs to TODAY's edition (tolerates GitHub's
    cron delays of up to 2 hours); later runs prepare tomorrow's edition.
    """
    now = (now or datetime.now(tz=LISBON_TZ)).astimezone(LISBON_TZ)
    close_hour = SEND_HOUR_LOCAL - WINDOW_CLOSES_BEFORE_SEND_H   # 05:00

    morning_cutoff = now.replace(hour=SEND_HOUR_LOCAL + 1, minute=0, second=0, microsecond=0)
    if now < morning_cutoff:
        edition_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        edition_day = (morning_cutoff + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    news_end = edition_day.replace(hour=close_hour, minute=0, second=0, microsecond=0)
    news_start = edition_day - timedelta(days=1)                  # yesterday 00:00 Lisbon
    return {
        "edition_day": edition_day,
        "news_start": news_start,
        "news_end": news_end,
        "events_start": news_end,
        "events_end": quarter_end(edition_day, offset=EVENT_LOOKAHEAD_QUARTERS),
    }


def quarter_end(d: datetime, offset: int = 0) -> datetime:
    """End of the quarter containing d (plus `offset` extra quarters), at 23:59:59 Lisbon."""
    year, q = d.year, (d.month - 1) // 3
    q += offset
    year += q // 4
    q %= 4
    last_month = 3 + q * 3                       # Mar, Jun, Sep, Dec
    if last_month == 12:
        first_of_next = datetime(year + 1, 1, 1, tzinfo=LISBON_TZ)
    else:
        first_of_next = datetime(year, last_month + 1, 1, tzinfo=LISBON_TZ)
    return first_of_next - timedelta(seconds=1)


# --- News queries (Google News RSS). Candidate themes; the composer
#     picks SECTIONS_ON_PAGE of them per edition for the front grid. ---
SECTIONS = {
    "Climate & Courts": [
        "climate lawsuit court ruling",
        "climate policy regulation government",
        "ICJ advisory opinion climate",
        "climate litigation human rights",
        "carbon emissions court order",
    ],
    "Energy & Business": [
        "renewable energy solar wind power",
        "corporate sustainability net zero ESG",
        "green hydrogen energy storage grid",
        "battery EV electric vehicle industry",
        "carbon credits offsets market",
    ],
    "Nature & Economy": [
        "deforestation biodiversity conservation",
        "climate economy finance world bank",
        "plastic pollution treaty oceans",
        "water scarcity drought agriculture",
        "critical minerals mining lithium cobalt",
    ],
    "Climate Science & Extreme Weather": [
        "IPCC climate report findings",
        "heatwave flood wildfire extreme weather attribution",
        "sea level rise glacier melting arctic",
        "carbon budget 1.5 degrees overshoot",
    ],
    "Politics & International": [
        "COP UN climate summit negotiation",
        "climate finance developing countries loss damage",
        "EU green deal CBAM regulation",
    ],
    "Food & Cities": [
        "sustainable agriculture food system emissions",
        "urban planning green building cities",
        "aviation shipping emissions fuel",
        "fast fashion textile waste",
    ],
    "Standards & Frameworks": [
        "GHG Protocol Scope 3 standard update",
        "CSRD ISSB sustainability disclosure standard",
        "science based targets SBTi",
        "AI model energy efficiency benchmark",
        "carbon accounting framework update",
        "greenwashing certification carbon neutral claim",
    ],
}

SECTIONS_ON_PAGE = 3               # themes the composer places on the grid
STORIES_PER_SECTION = 2
LEAD_QUERIES = [
    "climate change landmark ruling",
    "sustainability major announcement",
    "emissions record breaking climate",
]

# --- Big Tech, Cloud and AI ---
BIGTECH_COMPANIES = [
    "SAP", "Microsoft", "Amazon", "Google", "IBM", "OpenAI", "Anthropic",
    "Meta", "Nvidia", "Apple", "Tesla", "ByteDance", "Alibaba",
]
BIGTECH_QUERIES = [
    "Microsoft Google Amazon data center energy climate",
    "cloud computing sustainability carbon emissions",
    "OpenAI Anthropic data centre electricity",
    "SAP IBM sustainability environment",
    "AI data center power grid strain utility",
    "data center water usage cooling drought",
    "nuclear deal data center tech company",
    "Meta Nvidia AI energy consumption",
    "AI electricity demand forecast IEA",
    "AI climate modeling forecasting renewable energy grid",
]

# --- Events: upcoming sustainability events until the end of the quarter ---
EVENTS_QUERIES = [
    "sustainability conference congress announced",
    "climate summit schedule agenda",
    "AI for Good summit",
    "climate week sustainability event",
    "climate conference dates registration",
    "environmental award ceremony date",
]

# --- Research papers (Semantic Scholar) ---
PAPER_QUERIES = [
    "AI environmental impact carbon footprint",
    "machine learning energy efficiency training",
    "green AI sustainable computing",
    "AI climate change mitigation",
    "AI energy consumption measurement reporting framework",
    "benchmark large language model energy efficiency",
]
PAPER_FIELDS = "title,authors,externalIds,publicationDate,venue,abstract"
PAPER_MAX_AGE_DAYS = 7             # papers move slower than news
PAPERS_PER_EDITION = 5

RSS_ITEMS_PER_QUERY = 12
SNIPPET_MAX_CHARS = 700

# --- Publisher quality filter (Google News publisher names, word-boundary match) ---
# PUBLISHERS_ALLOW: if non-empty, ONLY stories from these publishers are kept.
# PUBLISHERS_BLOCK: always excluded, even if in the allow list.
# To switch to a softer block-list mode: empty PUBLISHERS_ALLOW and fill PUBLISHERS_BLOCK.
PUBLISHERS_ALLOW = [
    # wires
    "Reuters", "AP", "AFP", "Bloomberg",
    # majors
    "The Guardian", "BBC", "CNN", "CNBC", "Financial Times", "The New York Times",
    "The Washington Post", "Al Jazeera", "DW", "France 24", "Euronews", "NPR",
    "The Economist", "TIME", "The Independent", "The Telegraph", "Sky News",
    "Le Monde", "El Pais",
    # science & environment desks
    "Nature", "New Scientist", "Scientific American", "Phys.org", "ScienceDaily",
    "The Conversation", "National Geographic", "Live Science", "Yale Environment 360",
    # sustainability trade press
    "Carbon Brief", "Climate Home News", "Grist", "Inside Climate News",
    "Mongabay", "GreenBiz", "Canary Media", "Eco-Business", "Euractiv",
    "ESG Today", "BusinessGreen", "Sustainability Times", "Reuters Events",
    # tech / energy trade press (Big Tech & Cloud coverage)
    "Wired", "The Verge", "TechCrunch", "Ars Technica", "Data Center Dynamics",
    # institutions & broadcast majors
    "ABC News", "CBS News", "NBC News", "Axios", "Politico", "The Hill",
    "UN News", "World Bank", "IEA", "OECD", "UNEP",
]
PUBLISHERS_BLOCK = []
# If fewer than this many allow-listed stories are in the window, the fetch
# automatically admits other outlets as an "additional" tier (marked, and the
# composer is told to prefer trusted items and never lead with additional ones).
MIN_TRUSTED_NEWS = 8

# --- Dedupe: stories published in recent editions are never repeated ---
HISTORY_EDITIONS = 2
HISTORY_KEEP_EDITIONS = 14
