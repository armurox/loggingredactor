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

Python only applies the filter on that logger, so any other files using logging will not get the filter applied. To have this filter applied to all loggers do the following
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


## Release Notes - v0.0.5:

### Improvements and Changes
- Optimized function that applies the redaction (was setting the logger message value twice).
- Changed default_mask key initialization to mask
- Changed patterns key initialization to mask_patterns

### Bug Fixes
- Handled any exceptions related to deepcopies failing, related to attempt to redact IOStreams, including TypeError


## A Note about the Motivation behind Logging Redactor:
Logging Redactor started as a fork of [logredactor](https://pypi.org/project/logredactor/). However, due to the bugs present in the original (specifically the data mutations), it was not usable in production environments where the purpose was to only redact variables in the logs, not in their usage in the code. This, along with the fact that the original package is no longer maintained lead to the creation of Logging Redactor.
