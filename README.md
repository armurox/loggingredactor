# Logging Redactor

Redacts data in python logs based on regex filters or dictionary keys passed in by the user.  
This will work with json logging formats as well and also with nested data in the `extra` argument. 


# Examples

```python
import re
import logging
import loggingredactor

# Create a logger
logger = logging.getLogger()
# Add the redact filter to the logger with your custom filters
redact_patterns = [re.compile(r'\d+')]

# if no `default_mask` is passed in, 4 asterisks will be used
logger.addFilter(loggingredactor.RedactingFilter(redact_patterns, default_mask='xx'))

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
redact_patterns = [re.compile(r'(?<=api_key=)[\w-]+')]

# Override the logging handler that you want redacted
class RedactStreamHandler(logging.StreamHandler):
    def __init__(self, *args, **kwargs):
        logging.StreamHandler.__init__(self, *args, **kwargs)
        self.addFilter(loggingredactor.RedactingFilter(redact_patterns))

root_logger = logging.getLogger()

sys_stream = RedactStreamHandler()
# Also set the formatter to use json, this is optional and all nested keys will get redacted too
sys_stream.setFormatter(jsonlogger.JsonFormatter('%(name)s %(message)s'))
root_logger.addHandler(sys_stream)

logger = logging.getLogger(__name__)

logger.error("Request Failed", extra={'url': 'https://example.com?api_key=my-secret-key'})
# Output: {"name": "__main__", "message": "Request Failed", "url": "https://example.com?api_key=****"}
```

You can also redact by dictionary keys, rather than by regex, in cases where certain fields should always be redacted. To achieve this, you can provide any iterable represeting the keys that you would like to redact on. An exaple is shown below: 

```python
import re
import logging
import loggingredactor
from pythonjsonlogger import jsonlogger

# Create a pattern to hide api key in url. This uses a _Positive Lookbehind_
redact_keys = ['email', 'password']

# Override the logging handler that you want redacted
class RedactStreamHandler(logging.StreamHandler):
    def __init__(self, *args, **kwargs):
        logging.StreamHandler.__init__(self, *args, **kwargs)
        self.addFilter(loggingredactor.RedactingFilter(redact_patterns, mask_keys=redact_keys))

root_logger = logging.getLogger()

sys_stream = RedactStreamHandler()
# Also set the formatter to use json, this is optional and all nested keys will get redacted too
sys_stream.setFormatter(jsonlogger.JsonFormatter('%(name)s %(message)s'))
root_logger.addHandler(sys_stream)

logger = logging.getLogger(__name__)

logger.info("User %(firstname)s with email: %s and password: %s bought some food!", {'firstname': 'Arman', 'email': 'arman_jasuja@yahoo.com', 'password': '1234567'})
# Output: {"name": "__main__", "message": "User Arman with email: **** and password: **** bought some food"}
```