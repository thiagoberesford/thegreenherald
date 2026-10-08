"""Central configuration for The Green Herald."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# --- Brand & identity ---
BRAND = "The Green Herald"
TAGLINE = "All the news that the planet can afford to print"
DOMAIN = "thegreenherald.com"
EDITION_URL_BASE = "http://" + DOMAIN
# NOTE: http, not https, because the domain's certificate is not live yet.
# Once Settings -> Pages shows "Enforce HTTPS" and it is ticked, GitHub
# 301-redirects http -> https automatically, so these links keep working.
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

    The pipeline runs shortly after 05:00 for the 06:00 edition. Any time before
    today's release hour belongs to TODAY's edition; after it, to tomorrow's.
    """
    now = (now or datetime.now(tz=LISBON_TZ)).astimezone(LISBON_TZ)
    close_hour = SEND_HOUR_LOCAL - WINDOW_CLOSES_BEFORE_SEND_H   # 05:00

    today_release = now.replace(hour=SEND_HOUR_LOCAL, minute=0, second=0, microsecond=0)
    if now < today_release:
        edition_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        edition_day = (today_release + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    news_end = edition_day.replace(hour=close_hour, minute=0, second=0, microsecond=0)
    news_start = edition_day - timedelta(days=1)                  # yesterday 00:00 Lisbon
    return {
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

# --- Dedupe: stories published in recent editions are never repeated ---
HISTORY_EDITIONS = 2
HISTORY_KEEP_EDITIONS = 14
