import re

from .redacting_filter import RedactingFilter

# A standard email address pattern.
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# International phone numbers written with a '+' country code, e.g.
# "+1 415-555-2671", "+44 20 7946 0958", "+91-98765-43210", "+14155552671".
# Numbers written WITHOUT a leading '+' country code are intentionally not
# matched: a bare run of digits is indistinguishable from an order id, a date,
# an amount, etc., so matching it would redact far more than phone numbers.
PHONE = re.compile(
    r"(?<![\w+])"               # left boundary (not mid-word, not after a '+')
    r"\+\d{1,3}[\s.\-]?"        # '+' then 1-3 digit country code
    r"\(?\d{1,4}\)?[\s.\-]?"    # optional area code, optionally parenthesised
    r"\d{1,4}[\s.\-]?"          # a group of digits
    r"\d{1,9}"                  # the final group of digits
    r"(?!\d)"                   # right boundary (don't stop mid digit-run)
)

# Regex patterns applied to log *content* by CommonPIIRedactingFilter.
PII_PATTERNS = [EMAIL, PHONE]

# Dictionary / `extra` keys whose values are always masked by
# CommonPIIRedactingFilter, regardless of their content. Matched by exact key
# name (case-sensitive), so add casing variants you expect in your own logs.
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


class CommonPIIRedactingFilter(RedactingFilter):
    """A :class:`RedactingFilter` preloaded with common PII patterns and keys.

    The built-in content patterns (:data:`PII_PATTERNS`) and keys
    (:data:`PII_KEYS`) are always applied. Anything passed via ``mask_patterns``
    or ``mask_keys`` is *combined* with them rather than replacing them, so you
    keep the out-of-the-box coverage while adding your own.
    """

    def __init__(self, mask_patterns=None, mask='****', mask_keys=None, silent_failure=False):
        combined_patterns = list(PII_PATTERNS) + list(mask_patterns or [])
        combined_keys = set(PII_KEYS) | set(mask_keys or set())
        super().__init__(
            mask_patterns=combined_patterns,
            mask=mask,
            mask_keys=combined_keys,
            silent_failure=silent_failure,
        )
