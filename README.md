# Logging Redactor
![PyPI version](https://img.shields.io/pypi/v/loggingredactor.svg?color=blue)
![Supported Python versions](https://img.shields.io/pypi/pyversions/loggingredactor.svg?color=green)

Logging Redactor is a Python library designed to redact sensitive data in logs based on regex mask_patterns or dictionary keys. It supports JSON logging formats and handles nested data at the message level, at the positional argument level and also in the `extra` keyword argument.

## Installation

You can install Logging Redactor via pip:

```
pip install loggingredactor
```

## Illustrative Examples

Below is a basic example that illustrates how to redact any digits in a logger message:

```python
import re
import logging
import loggingredactor

# Create a logger
logger = logging.getLogger()
# Add the redact filter to the logger with your custom filters
redact_mask_patterns = [re.compile(r'\d+')]

# if no `mask` is passed in, 4 asterisks will be used
logger.addFilter(loggingredactor.RedactingFilter(redact_mask_patterns, mask='xx'))

logger.warning("This is a test 123...")
# Output: This is a test xx...
```

Python only applies the filter on that logger, so any other files using logging will not get the filter applied. To have this filter applied to all loggers do the following (note that you must first run 
`pip install python-json-logger`
to use this example
)
```python
import re
import logging
import loggingredactor
from pythonjsonlogger import jsonlogger

# Create a pattern to hide api key in url. This uses a _Positive Lookbehind_
redact_mask_patterns = [re.compile(r'(?<=api_key=)[\w-]+')]

# Override the logging handler that you want redacted
class RedactStreamHandler(logging.StreamHandler):
    def __init__(self, *args, **kwargs):
        logging.StreamHandler.__init__(self, *args, **kwargs)
        self.addFilter(loggingredactor.RedactingFilter(redact_mask_patterns))

root_logger = logging.getLogger()

sys_stream = RedactStreamHandler()
# Also set the formatter to use json, this is optional and all nested keys will get redacted too
sys_stream.setFormatter(jsonlogger.JsonFormatter('%(name)s %(message)s'))
root_logger.addHandler(sys_stream)

logger = logging.getLogger(__name__)

logger.error("Request Failed", extra={'url': 'https://example.com?api_key=my-secret-key'})
# Output: {"name": "__main__", "message": "Request Failed", "url": "https://example.com?api_key=****"}
```

You can also redact by dictionary keys, rather than by regex, in cases where certain fields should always be redacted. To achieve this, you can provide any iterable representing the keys that you would like to redact on. An example is shown below (this time with a different default mask): 

```python
import re
import logging
import loggingredactor
from pythonjsonlogger import jsonlogger

# This list now contains all the dictioanry keys that will have their values redacted in the logger object
redact_keys = ['email', 'password']

# Override the logging handler that you want redacted
class RedactStreamHandler(logging.StreamHandler):
    def __init__(self, *args, **kwargs):
        logging.StreamHandler.__init__(self, *args, **kwargs)
        self.addFilter(loggingredactor.RedactingFilter(mask='REDACTED', mask_keys=redact_keys))

root_logger = logging.getLogger()

sys_stream = RedactStreamHandler()
# Also set the formatter to use json, this is optional and all nested keys will get redacted too
sys_stream.setFormatter(jsonlogger.JsonFormatter('%(name)s %(message)s'))
root_logger.addHandler(sys_stream)

logger = logging.getLogger(__name__)

logger.warning("User %(firstname)s with email: %(email)s and password: %(password)s bought some food!", {'firstname': 'Arman', 'email': 'arman_jasuja@yahoo.com', 'password': '1234567'})
# Output: {"name": "__main__", "message": "User Arman with email: REDACTED and password: REDACTED bought some food"}
```
The above example also illustrates the logger redacting positional arguments provided to the message.

### Integrating with already built logger configs
Logging Redactor also integrates quite well with already created logging configurations, for example, say you have your logging config set up in the following format:
```python
import re
import logging.config
... # Other imports
LOGGING = {
    ... # Your other configs
    'filters':{ 
        ... # Some configs
        'pii': {
            '()': 'loggingredactor.RedactingFilter',
            'mask_keys': ('password', 'email', 'last_name', 'first_name', 'gender', 'lastname', 'firstname',),
            'mask_patterns': (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), ) # email regex
            'mask': 'REDACTED',
        },
        ... # Some other configs
    }
    'handlers': {
        ... # Some handlers
        'stdout': {
            ... # Some configs
            'filters': ['pii', ...],
        },
        ... # Other handlers (add pii as a filter to all the ones where you want the appropriate information to be redacted)
    }
    ... # Rest of your configs
}

logging.config.dictConfig(LOGGING)
... # Use your logger as normal, the redaction will now be applied.
```
The essence boils down to adding the RedactingFilter to your logging config, and to the filters section of the associated handlers to which you want to apply the redaction.

### Redacting common PII out of the box
If you don't want to assemble your own patterns and keys, use `CommonPIIRedactingFilter`. It comes preloaded with patterns and keys for the most common kinds of PII, and **combines** anything you pass in with those built-ins (so you keep the defaults *and* add your own):

```python
import re
import logging
import loggingredactor

logger = logging.getLogger("demo")
logger.addFilter(loggingredactor.CommonPIIRedactingFilter(
    mask="REDACTED",
    # both optional, and combined with the built-ins rather than replacing them:
    mask_patterns=[re.compile(r"SECRET-\w+")],
    mask_keys={"order_token"},
))

logger.warning("contact %s or %s", "arman@example.com", "+1 415-555-2671")
# Output: contact REDACTED or REDACTED

logger.warning("login %(password)s", {"password": "hunter2"})
# Output: login REDACTED
```

The patterns and keys are also importable directly, if you'd rather reuse them in a plain `RedactingFilter`:

```python
from loggingredactor import common_pii_filters

common_pii_filters.EMAIL         # compiled email regex
common_pii_filters.PHONE         # compiled international phone regex
common_pii_filters.PII_PATTERNS  # [EMAIL, PHONE]
common_pii_filters.PII_KEYS      # {'password', 'token', 'ssn', ...}
```

#### What it does and does not redact
**Content patterns** (`PII_PATTERNS`) are matched anywhere in the logged text:

| Pattern | Redacts | Does **not** redact |
| --- | --- | --- |
| `EMAIL` | Standard email addresses, e.g. `arman@example.com` | Malformed addresses (`a@b`, no TLD) |
| `PHONE` | International numbers with a `+` country code, e.g. `+1 415-555-2671`, `+44 20 7946 0958`, `+91-98765-43210` | Bare local numbers with no `+` country code (`4155552671`, `(415) 555-2671`) — deliberately, so order ids, dates and amounts aren't redacted |

**Keys** (`PII_KEYS`) mask the whole value whenever a dict / `extra` key matches by **exact, case-sensitive** name: `password`, `passwd`, `pwd`, `secret`, `token`, `access_token`, `refresh_token`, `api_key`, `apikey`, `authorization`, `auth`, `session`, `session_id`, `cookie`, `email`, `phone`, `phone_number`, `phonenumber`, `ssn`, `social_security_number`, `credit_card`, `card_number`, `cvv`, `first_name`, `firstname`, `last_name`, `lastname`.

Because key matching is exact and case-sensitive, if your logs use other casings or spellings (e.g. `Password`, `userEmail`) pass them via `mask_keys` to extend the set.

### Failing safely
If redaction ever raises while processing a record, loggingredactor will **not** crash your application: the record is still emitted, and the error is reported via `logger.exception` on the originating logger. If you'd rather suppress that error log entirely, pass `silent_failure=True` (available on both filters):

```python
loggingredactor.RedactingFilter(mask_patterns, silent_failure=True)
loggingredactor.CommonPIIRedactingFilter(silent_failure=True)
```


## Release Notes - v0.0.7:

### Improvements and Changes
- Added support for Python 3.13 and 3.14. (Reported in issue [#13](https://github.com/armurox/loggingredactor/issues/13))
- Added `CommonPIIRedactingFilter`, a filter preloaded with common PII patterns (email and international phone numbers) and keys (passwords, tokens, etc.). User-supplied `mask_patterns`/`mask_keys` are combined with the built-ins rather than replacing them. The patterns and keys are also exposed via `loggingredactor.common_pii_filters`.
- Added a `silent_failure` keyword argument (default `False`) to both filters to suppress the error log emitted when redacting a record fails.

### Bug Fixes
- Redact sensitive data exposed through an object's `str`/`repr` when it is logged, even if the object's type is not one of the explicitly handled types (e.g. a custom class whose `__str__` returns an email). The original object is left untouched, and numeric conversions such as `%d`/`%f` continue to use the real value since only `__str__`/`__repr__` are redacted. (Reported in issue [#12](https://github.com/armurox/loggingredactor/issues/12))
- Support mapping types with non-standard constructors, such as Django's `QueryDict`. (Reported in issue [#14](https://github.com/armurox/loggingredactor/issues/14))
- Application crashes due to errors in loggingredactor no longer occur. loggingredactor will produce a handled `logger.exception` on the originating logger and logging continues with the record otherwise intact. (Reported in issue [#14](https://github.com/armurox/loggingredactor/issues/14))


## A Note about the Motivation behind Logging Redactor:
Logging Redactor started as a fork of [logredactor](https://pypi.org/project/logredactor/). However, due to the bugs present in the original (specifically the data mutations), it was not usable in production environments where the purpose was to only redact variables in the logs, not in their usage in the code. This, along with the fact that the original package is no longer maintained lead to the creation of Logging Redactor.
