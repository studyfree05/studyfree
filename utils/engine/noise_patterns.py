"""
noise_patterns.py
-----------------

Common promotional and greeting phrases found in YouTube videos.

Supported Languages
-------------------
- English
- Telugu
- Hindi
"""

# ======================================================
# ENGLISH
# ======================================================

ENGLISH_NOISE = [

    # Greetings
    r"welcome\s+back",
    r"welcome\s+everyone",
    r"welcome\s+to\s+the\s+channel",
    r"hello\s+everyone",
    r"hi\s+everyone",
    r"good\s+morning",
    r"good\s+afternoon",
    r"good\s+evening",
    r"hope\s+you\s+are\s+doing\s+well",

    # Like / Share / Subscribe
    r"please\s+like\s+the\s+video",
    r"like\s+the\s+video",
    r"like\s+this\s+video",
    r"please\s+subscribe",
    r"subscribe\s+to\s+the\s+channel",
    r"subscribe\s+my\s+channel",
    r"don't\s+forget\s+to\s+subscribe",
    r"share\s+this\s+video",
    r"share\s+the\s+video",
    r"hit\s+the\s+bell\s+icon",
    r"press\s+the\s+bell\s+icon",
    r"turn\s+on\s+notifications",

    # Social Media
    r"join\s+our\s+telegram",
    r"join\s+telegram",
    r"follow\s+me\s+on\s+instagram",
    r"follow\s+us\s+on\s+instagram",
    r"join\s+our\s+whatsapp\s+group",
    r"follow\s+our\s+facebook\s+page",

    # Misc
    r"link\s+in\s+the\s+description",
    r"check\s+the\s+description",
    r"comment\s+below",
    r"thanks\s+for\s+watching",
    r"thank\s+you\s+for\s+watching",
]

# ======================================================
# TELUGU
# ======================================================

TELUGU_NOISE = [

    # Greetings
    r"అందరికీ\s*నమస్కారం",
    r"నమస్కారం",
    r"హలో\s*ఫ్రెండ్స్",
    r"వెల్కమ్\s*బ్యాక్",
    r"మన\s*ఛానల్\s*కి\s*స్వాగతం",

    # Like / Share / Subscribe
    r"వీడియోని\s*లైక్\s*చేయండి",
    r"లైక్\s*చేయండి",
    r"వీడియో\s*లైక్\s*చేయండి",
    r"షేర్\s*చేయండి",
    r"సబ్స్క్రైబ్\s*చేయండి",
    r"చానల్\s*ని\s*సబ్స్క్రైబ్\s*చేయండి",
    r"బెల్\s*ఐకాన్\s*ప్రెస్\s*చేయండి",
    r"బెల్\s*ఐకాన్\s*నొక్కండి",

    # Social Media
    r"టెలిగ్రామ్\s*జాయిన్\s*అవ్వండి",
    r"టెలిగ్రామ్\s*గ్రూప్\s*జాయిన్\s*అవ్వండి",
    r"వాట్సాప్\s*గ్రూప్\s*జాయిన్\s*అవ్వండి",
    r"ఇన్‌స్టాగ్రామ్\s*ఫాలో\s*చేయండి",
    r"ఫేస్‌బుక్\s*ఫాలో\s*చేయండి",

    # Misc
    r"డిస్క్రిప్షన్\s*లో\s*లింక్\s*ఉంది",
    r"కింద\s*కామెంట్\s*చేయండి",
    r"చూసినందుకు\s*ధన్యవాదాలు",
]

# ======================================================
# HINDI
# ======================================================

HINDI_NOISE = [

    # Greetings
    r"नमस्कार",
    r"नमस्ते",
    r"हेलो\s+दोस्तों",
    r"आप\s+सभी\s+का\s+स्वागत\s+है",
    r"स्वागत\s+है",
    r"वेलकम\s+बैक",

    # Like / Share / Subscribe
    r"वीडियो\s+को\s+लाइक\s+करें",
    r"लाइक\s+करें",
    r"वीडियो\s+को\s+शेयर\s+करें",
    r"शेयर\s+करें",
    r"चैनल\s+को\s+सब्सक्राइब\s+करें",
    r"सब्सक्राइब\s+करें",
    r"बेल\s+आइकन\s+दबाएं",
    r"नोटिफिकेशन\s+ऑन\s+करें",

    # Social Media
    r"टेलीग्राम\s+जॉइन\s+करें",
    r"व्हाट्सएप\s+ग्रुप\s+जॉइन\s+करें",
    r"इंस्टाग्राम\s+फॉलो\s+करें",
    r"फेसबुक\s+फॉलो\s+करें",

    # Misc
    r"डिस्क्रिप्शन\s+में\s+लिंक\s+है",
    r"नीचे\s+कमेंट\s+करें",
    r"देखने\s+के\s+लिए\s+धन्यवाद",
]

# ======================================================
# ALL LANGUAGES
# ======================================================

NOISE_PATTERNS = (
    ENGLISH_NOISE +
    TELUGU_NOISE +
    HINDI_NOISE
)


