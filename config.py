"""Central configuration for The Green Herald."""

BRAND = "The Green Herald"
TAGLINE = "All the news that the planet can afford to print"
DOMAIN = "thegreenherald.com"
EDITION_URL_BASE = "https://" + DOMAIN          # web editions live at https://thegreenherald.com/YYYY-MM-DD.html

TIMEZONE = "Europe/Lisbon"
SEND_HOUR_LOCAL = 6                              # email lands at 06:00 Lisbon
WINDOW_CLOSES_BEFORE_SEND_H = 1                  # news window closes at 05:00 Lisbon

# --- LLM ---
LLM_MODEL = "mistral-small-latest"               # change to a free-tier model if you prefer
LLM_MAX_TOKENS = 4096

# --- News queries (Google News RSS) ---
SECTIONS = {
    "Climate & Courts": [
        "climate lawsuit court ruling",
        "climate policy regulation government",
    ],
    "Energy & Business": [
        "renewable energy solar wind power",
        "corporate sustainability net zero ESG",
    ],
    "Nature & Economy": [
        "deforestation biodiversity conservation",
        "climate economy finance world bank",
    ],
}

LEAD_QUERIES = [
    "climate change landmark ruling",
    "sustainability major announcement",
]

BIGTECH_COMPANIES = [
    "SAP", "Microsoft", "Amazon", "Google", "IBM", "OpenAI", "Anthropic",
]
BIGTECH_QUERIES = [
    "Microsoft Google Amazon data center energy climate",
    "cloud computing sustainability carbon emissions",
    "OpenAI Anthropic data centre electricity",
    "SAP IBM sustainability environment",
]

PAPER_QUERY = "climate sustainability AI"
PAPER_FIELDS = "title,authors,externalIds,publicationDate,venue"
PAPERS_PER_EDITION = 5

STORIES_PER_SECTION = 2
BIGTECH_STORIES = 3
RSS_ITEMS_PER_QUERY = 12
SNIPPET_MAX_CHARS = 700
