"""
config.py
---------

Central configuration for the AI Quiz Engine.
Change models here only.
"""

# ==========================
# OLLAMA
# ==========================

OLLAMA_URL = "http://localhost:11434"


# ==========================
# MODELS
# ==========================

# Fast model for understanding lessons
KNOWLEDGE_MODEL = "qwen2.5:3b"

# Better model for writing questions
QUESTION_MODEL = "qwen2.5:3b"

# ==========================
# CACHE
# ==========================

CACHE_DIR = "utils/engine/cache"

KNOWLEDGE_CACHE = f"{CACHE_DIR}/knowledge"

QUESTION_CACHE = f"{CACHE_DIR}/questions"

# ==========================
# REQUESTS
# ==========================

TIMEOUT = 300

# ==========================
# KNOWLEDGE
# ==========================

MAX_TOPICS = 8

MAX_KEYPOINTS = 5

SUMMARY_WORDS = 80

# ==========================
# QUESTIONS
# ==========================

DEFAULT_QUESTIONS = 25

MAX_OPTIONS = 4

DIFFICULTY = "medium"


# ==========================
# AI PROVIDERS
# ==========================

# Paid API fallback is OFF by default.
# Free providers should always be tried first.
ALLOW_PAID_FALLBACK = False

# Extra protection for when paid fallback
# is deliberately enabled later.
MAX_PAID_REQUESTS_PER_DAY = 3

# Local Ollama remains the final offline fallback.
ALLOW_OLLAMA_FALLBACK = True