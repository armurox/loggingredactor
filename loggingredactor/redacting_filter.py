import re
import logging
import copy
from collections.abc import Mapping


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
        self._subclass_cache = {}

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
            if isinstance(content_copy, Mapping):  # Covers all dict-like objects
                content_copy = type(content_copy)([
                    (k, self._mask if k in self._mask_keys else self.redact(v))
                    for k, v in content_copy.items()
                ])

            elif isinstance(content_copy, list):
                content_copy = [self.redact(value) for value in content_copy]

            elif isinstance(content_copy, tuple):
                content_copy = tuple(self.redact(value) for value in content_copy)

            # Support for keys in extra field
            elif key and key in self._mask_keys:
                content_copy = self._mask

            elif isinstance(content_copy, str):
                content_copy = self._apply_patterns(content_copy)

            # Any other object may expose data to be redacted through its
            # str/repr. _redact_repr only redacts objects it can safely re-tag
            # (so numeric conversions like %d/%f keep working). Anything it
            # cannot handle - numbers, bytes, C types, __slots__ objects - is
            # left untouched rather than guessing based on its type.
            else:
                content_copy = self._redact_repr(content_copy)

        return content_copy

    def _apply_patterns(self, text):
        for pattern in self._mask_patterns:
            text = re.sub(pattern, self._mask, text)
        return text

    def _redacting_subclass(self, base):
        cached = self._subclass_cache.get(base)
        if cached is not None:
            return cached
        subclass = type('Redacted%s' % base.__name__, (base,), {
            '__str__': lambda self: self._lr_str,
            '__repr__': lambda self: self._lr_repr,
        })
        self._subclass_cache[base] = subclass
        return subclass

    def _redact_repr(self, obj):
        try:
            original_str = str(obj)
            original_repr = repr(obj)
        except Exception:
            return obj

        redacted_str = self._apply_patterns(original_str)
        redacted_repr = self._apply_patterns(original_repr)
        if redacted_str == original_str and redacted_repr == original_repr:
            return obj

        # We're subclassing the class and replacing it rather
        # than doing it directly on the class to avoid affecting
        # all original instances of the object basically
        try:
            obj._lr_str = redacted_str
            obj._lr_repr = redacted_repr
            obj.__class__ = self._redacting_subclass(type(obj))
            return obj
        except Exception:
            return obj
