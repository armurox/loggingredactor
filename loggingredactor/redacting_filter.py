import re
import logging
import copy
from collections.abc import Mapping
from collections.abc import Sequence
from collections.abc import Set


class RedactingFilter(logging.Filter):
    # Do not try and redact the built in values. With the wrong regex it can break the logging
    ignore_keys = {
        'name', 'levelname', 'levelno', 'pathname', 'filename', 'module',
        'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName', 'created',
        'msecs', 'relativeCreated', 'thread', 'threadName', 'process',
        'processName',
    }

    # Set on our own logging records so we skip them (no re-redaction / recursion).
    _internal_flag = '_loggingredactor_internal'

    # Registered sequences that are logically scalar (text, binary, numeric
    # range): redact via patterns/repr, don't recurse into their elements.
    _atomic_iterables = (str, bytes, bytearray, memoryview, range)

    def __init__(self, mask_patterns='', mask='****', mask_keys=None, silent_failure=False):
        super(RedactingFilter, self).__init__()
        self._mask_patterns = mask_patterns
        self._mask = str(mask)
        self._mask_keys = set(mask_keys or {})
        self._silent_failure = silent_failure
        self._subclass_cache = {}

    def filter(self, record):
        if getattr(record, self._internal_flag, False):
            return True

        d = vars(record)
        for k, content in d.items():
            if k in self.ignore_keys:
                continue
            try:
                d[k] = self.redact(content, k)
            except Exception:
                # We should never crash the app on a redaction failure.
                if not self._silent_failure:
                    logging.getLogger(record.name).exception(
                        '[%s.%s] Could not redact logs due to an error!',
                        type(self).__module__,
                        type(self).__qualname__,
                        extra={self._internal_flag: True},
                    )

        return True

    def redact(self, content, key=None):
        try:
            content_copy = copy.deepcopy(content)
        except Exception:
            return content
        if content_copy:
            if isinstance(content_copy, Mapping):  # Covers all dict-like objects
                content_copy = self._redact_mapping(content_copy)

            # Recurse into standard containers. We match Sequence/Set (which
            # require registration), not the duck-typed Collection, so costly or
            # side-effecting third-party iterables (Django QuerySet hitting the
            # DB, numpy arrays, ...) are left to _redact_representation instead.
            elif (isinstance(content_copy, (Sequence, Set))
                    and not isinstance(content_copy, self._atomic_iterables)):
                content_copy = self._redact_iterable(content_copy)

            # Support for keys in extra field
            elif key and key in self._mask_keys:
                content_copy = self._mask

            elif isinstance(content_copy, str):
                content_copy = self._apply_patterns(content_copy)

            # Other objects may leak via str/repr; _redact_representation handles those it
            # can safely re-tag and leaves the rest (numbers, C types, etc) alone.
            else:
                content_copy = self._redact_representation(content_copy)

        return content_copy

    def _redact_mapping(self, mapping):
        items = [
            (k, self._mask if k in self._mask_keys else self.redact(v))
            for k, v in mapping.items()
        ]
        # Mutates in place to keep the exact type and avoid non-standard
        # constructors like Django's QueryDict (issue #14).
        try:
            for k, v in items:
                mapping[k] = v
            return mapping
        except Exception:
            pass
        # For immutable mappings (e.g. frozendict) we rebuild.
        try:
            return type(mapping)(items)
        except Exception:
            pass
        try:
            return type(mapping)(dict(items))
        except Exception:
            pass
        # Keep the redacted data even if the original type is lost.
        return dict(items)

    def _redact_iterable(self, iterable):
        items = [self.redact(value) for value in iterable]
        make = getattr(type(iterable), '_make', None)  # namedtuple support
        if make is not None:
            try:
                return make(items)
            except Exception:
                pass
        # Rebuild the original type (list, tuple, set, frozenset, deque, ...),
        # falling back to a list when it can't be reconstructed.
        try:
            return type(iterable)(items)
        except Exception:
            return items

    def _apply_patterns(self, text):
        for pattern in self._mask_patterns:
            # A pattern is either a regex or a callable redactor (text, mask).
            if callable(pattern):
                text = pattern(text, self._mask)
            else:
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

    def _redact_representation(self, obj):
        try:
            original_str = str(obj)
            original_repr = repr(obj)
        except Exception:
            return obj

        redacted_str = self._apply_patterns(original_str)
        redacted_repr = self._apply_patterns(original_repr)
        if redacted_str == original_str and redacted_repr == original_repr:
            return obj

        # Swap to a per-type subclass (not the original class) so only this
        # instance's str/repr change, not every instance of its type.
        try:
            obj._lr_str = redacted_str
            obj._lr_repr = redacted_repr
            obj.__class__ = self._redacting_subclass(type(obj))
            return obj
        except Exception:
            return obj
