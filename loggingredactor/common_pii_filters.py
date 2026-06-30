import re
import importlib.util

from .redacting_filter import RedactingFilter

EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

_B = r"(?<![\w+])"   # not mid-word, not right after a '+'
_E = r"(?!\d)"       # don't stop in the middle of a digit run


class PHONE:
    """Curated phone-number regexes keyed by ISO 3166-1 alpha-2 country code,
    plus ``INTERNATIONAL`` for any ``+CC`` number.

    Each matches the country's ``+<country code>`` form and, where the country
    uses a ``0`` trunk prefix, its common local format. They favour precision;
    for full coverage and validation install ``phonenumbers`` (see
    :class:`CommonPIIRedactingFilter`).
    """

    INTERNATIONAL = re.compile(
        _B + r"\+\d{1,3}[\s.\-]?\(?\d{1,4}\)?[\s.\-]?\d{1,4}[\s.\-]?\d{1,9}" + _E
    )
    US = re.compile(_B + r"(?:\+1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}" + _E)
    GB = re.compile(_B + r"(?:\+44[\s.\-]?|0)(?:\d[\s.\-]?){8,9}\d" + _E)
    DE = re.compile(_B + r"(?:\+49[\s.\-]?|0)(?:\d[\s.\-]?){5,12}\d" + _E)
    FR = re.compile(_B + r"(?:\+33[\s.\-]?|0)(?:\d[\s.\-]?){8}\d" + _E)
    IN = re.compile(_B + r"(?:\+91[\s.\-]?|0)\d{5}[\s.\-]?\d{5}" + _E)
    AE = re.compile(_B + r"(?:\+971[\s.\-]?|0)(?:\d[\s.\-]?){7,8}\d" + _E)
    AU = re.compile(_B + r"(?:\+61[\s.\-]?|0)(?:\d[\s.\-]?){8}\d" + _E)


PHONE_PATTERNS = {
    name: value for name, value in vars(PHONE).items()
    if isinstance(value, re.Pattern)
}

PII_PATTERNS = [EMAIL] + list(PHONE_PATTERNS.values())

# Masked by exact, case-sensitive key name.
PII_KEYS = {
    'password', 'passwd', 'pwd',
    'secret', 'token', 'access_token', 'refresh_token',
    'api_key', 'apikey', 'authorization', 'auth',
    'session', 'session_id', 'cookie',
    'email', 'phone', 'phone_number', 'phonenumber',
    'ssn', 'social_security_number',
    'credit_card', 'card_number', 'cvv',
    'first_name', 'firstname', 'last_name', 'lastname',
}


def _phonenumbers_redactor(regions):
    def redact(text, mask):
        import phonenumbers  # optional dependency, imported only on this path

        spans = []
        for region in regions:
            try:
                spans.extend(
                    (m.start, m.end)
                    for m in phonenumbers.PhoneNumberMatcher(text, region)
                )
            except Exception:
                continue
        if not spans:
            return text
        spans.sort()
        merged = [spans[0]]
        for start, end in spans[1:]:
            if start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        # Replace right-to-left so earlier spans' offsets stay valid.
        for start, end in reversed(merged):
            text = text[:start] + mask + text[end:]
        return text

    return redact


def _build_phone_patterns(phone_regions):
    if phone_regions is None:
        return list(PHONE_PATTERNS.values())

    regions = [region.upper() for region in phone_regions]
    if importlib.util.find_spec('phonenumbers') is not None:
        return [_phonenumbers_redactor(regions)]
    return [PHONE_PATTERNS[region] for region in regions if region in PHONE_PATTERNS]


class CommonPIIRedactingFilter(RedactingFilter):
    """A :class:`RedactingFilter` preloaded with common PII patterns and keys.

    The built-in patterns (email + phone) and keys (:data:`PII_KEYS`) are always
    applied; ``mask_patterns`` / ``mask_keys`` are combined with them, not
    replacing them.

    ``phone_regions`` is ``None`` for every curated region plus international
    ``+CC`` numbers, or a list of ISO 3166-1 alpha-2 codes to limit it to those
    (using ``phonenumbers`` for validated detection when it is installed).
    """

    def __init__(self, mask_patterns=None, mask='****', mask_keys=None,
                 silent_failure=False, phone_regions=None):
        combined_patterns = (
            [EMAIL] + _build_phone_patterns(phone_regions) + list(mask_patterns or [])
        )
        combined_keys = set(PII_KEYS) | set(mask_keys or set())
        super().__init__(
            mask_patterns=combined_patterns,
            mask=mask,
            mask_keys=combined_keys,
            silent_failure=silent_failure,
        )
