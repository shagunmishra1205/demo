"""Sample forms, mirroring SAMPLE_FORMS in the frontend's js/data.js."""


def _opt(v, en, hi=None):
    return {"v": v, "en": en, "hi": hi or en}


def _f(id, type, required, en, hi, **extra):
    return {"id": id, "type": type, "required": required, "label": {"en": en, "hi": hi}, **extra}


SAMPLE_FORMS = {
    "scholar": {
        "id": "scholar",
        "title": {"en": "Scholarship form", "hi": "छात्रवृत्ति फॉर्म"},
        "fields": [
            _f("name", "text", True, "What is your full name?", "आपका पूरा नाम क्या है?",
               hint={"en": "Write it the same way as on your school certificate.",
                     "hi": "वैसे ही बताइए जैसा स्कूल प्रमाणपत्र में लिखा है।"}),
            _f("dob", "date", True, "What is your date of birth?", "आपकी जन्मतिथि क्या है?",
               hint={"en": "Say it like 15 August 2008, or type 15/08/2008.",
                     "hi": "जैसे 15 अगस्त 2008 या 15/08/2008।"}),
            _f("father", "text", True, "What is your father's name?", "आपके पिता का नाम क्या है?"),
            _f("income", "select", True, "What is your family's yearly income?", "परिवार की सालाना आय कितनी है?",
               options=[_opt("below_1l", "Below ₹1 lakh", "₹1 लाख से कम"),
                        _opt("1_to_2_5l", "₹1 to ₹2.5 lakh", "₹1 से ₹2.5 लाख"),
                        _opt("2_5_to_5l", "₹2.5 to ₹5 lakh", "₹2.5 से ₹5 लाख"),
                        _opt("above_5l", "Above ₹5 lakh", "₹5 लाख से ज़्यादा")]),
            _f("category", "select", True, "Which category are you in?", "आप किस वर्ग से हैं?",
               options=[_opt("General", "General", "सामान्य"), _opt("OBC", "OBC"),
                        _opt("SC", "SC"), _opt("ST", "ST")]),
            _f("phone", "phone", True, "What is your mobile number?", "आपका मोबाइल नंबर क्या है?",
               hint={"en": "10 digits. Example: 98765 43210", "hi": "10 अंक। जैसे 98765 43210"}),
            _f("email", "email", False, "What is your email address?", "आपका ईमेल पता क्या है?"),
            _f("pin", "pin", True, "What is your PIN code?", "आपका पिन कोड क्या है?",
               hint={"en": "6 digits", "hi": "6 अंक"}),
            _f("aadhaar", "sensitive", False, "What is your Aadhaar number?", "आपका आधार नंबर क्या है?",
               hint={"en": "This is private. It stays hidden on screen.",
                     "hi": "यह निजी है। स्क्रीन पर छिपा रहेगा।"}),
        ],
    },
    "camp": {
        "id": "camp",
        "title": {"en": "Health camp form", "hi": "स्वास्थ्य शिविर फॉर्म"},
        "fields": [
            _f("name", "text", True, "What is your name?", "आपका नाम क्या है?"),
            _f("age", "number", True, "How old are you?", "आपकी उम्र कितनी है?",
               hint={"en": "Say or type your age in years.", "hi": "अपनी उम्र साल में बताएँ।"}),
            _f("blood", "select", False, "What is your blood group?", "आपका ब्लड ग्रुप क्या है?",
               options=[_opt(g, g) for g in ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]]
                       + [_opt("unknown", "Don't know", "मालूम नहीं")]),
            _f("village", "text", True, "Which village do you live in?", "आप किस गाँव में रहते हैं?"),
            _f("pin", "pin", True, "What is your PIN code?", "आपका पिन कोड क्या है?"),
            _f("phone", "phone", True, "What is your mobile number?", "आपका मोबाइल नंबर क्या है?"),
            _f("date", "date", True, "Which date would you like to come to the camp?",
               "शिविर में आने की कौन सी तारीख चुनेंगे?",
               hint={"en": "Example: 12/12/2026", "hi": "जैसे 12/12/2026"}),
        ],
    },
}
