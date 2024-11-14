import re
import logging
import copy


class RedactingFilter(logging.Filter):
    # Do not try and redact the built in values. With the wrong regex it can break the logging
    ignore_keys = {
        'name', 'levelname', 'levelno', 'pathname', 'filename', 'module',
        'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName', 'created',
        'msecs', 'relativeCreated', 'thread', 'threadName', 'process',
        'processName',
    }

    def __init__(self, mask_patterns='', mask='****', mask_keys=None):
        super(RedactingFilter, self).__init__()
        self._mask_patterns = mask_patterns
        self._mask = str(mask)
        self._mask_keys = set(mask_keys or {})

    def filter(self, record):
        d = vars(record)
        for k, content in d.items():
            if k not in self.ignore_keys:
                d[k] = self.redact(content, k)

        return True

    def redact(self, content, key=None):
        try:
            content_copy = copy.deepcopy(content)
        except Exception:
            return content
        if content_copy:
            if isinstance(content_copy, dict):
                for k, v in content_copy.items():
                    content_copy[k] = self._mask if k in self._mask_keys else self.redact(v)

            elif isinstance(content_copy, list):
                content_copy = [self.redact(value) for value in content_copy]

            elif isinstance(content, tuple):
                content_copy = tuple(self.redact(value) for value in content_copy)

            # Support for keys in extra field
            elif key and key in self._mask_keys:
                content_copy = self._mask

            else:
                content_copy = isinstance(content_copy, str) and content_copy or str(content_copy)
                for pattern in self._mask_patterns:
                    content_copy = re.sub(pattern, self._mask, content_copy)

        return content_copy
