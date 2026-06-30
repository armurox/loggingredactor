import re
import pytest
import logging
import loggingredactor
from frozendict import frozendict
from collections import OrderedDict, UserDict, ChainMap, namedtuple, deque
from collections.abc import Mapping
from types import MappingProxyType

MAPPING_TYPES = [dict, OrderedDict, UserDict, ChainMap, frozendict, MappingProxyType]


try:
    import django.conf
    if not django.conf.settings.configured:
        django.conf.settings.configure(DEFAULT_CHARSET='utf-8')
    from django.http import QueryDict
    HAS_DJANGO = True
except Exception:
    HAS_DJANGO = False


class QueryDictLike(dict):
    """Mimics Django's QueryDict: the constructor parses a query string, so
    passing a list of (key, value) tuples (the old rebuild strategy) raises."""

    def __init__(self, query_string='', mutable=True):
        super().__init__()
        for pair in filter(None, query_string.split('&')):
            key, _, value = pair.partition('=')
            super().__setitem__(key, value)


class ExplodingMapping(Mapping):
    """A mapping whose iteration blows up, to exercise the filter's safety net."""

    def __getitem__(self, key):
        raise KeyError(key)

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 1  # non-empty so redact() actually processes it

    def items(self):
        raise RuntimeError('boom')

    def __deepcopy__(self, memo):
        return self


class CustomRedactingFilter(loggingredactor.RedactingFilter):
    """Subclass used to verify error reporting uses the runtime class name."""


@pytest.fixture
def logger_setup(request):
    def get_logger(filters=''):
        # Use the test functions name to get a unique logger for that test
        logger = logging.getLogger(request.node.name)
        logger.addFilter(
            loggingredactor.RedactingFilter(
                filters,
                mask='****',
                mask_keys={'phonenumber', }
            )
        )
        return logger

    return get_logger


def test_no_args_and_no_pattern(caplog, logger_setup):
    logger = logger_setup()
    temp = "foo12bar"
    logger.warning(temp)
    assert caplog.records[0].message == "foo12bar"
    assert temp == "foo12bar"


def test_no_args(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{2}')])
    temp = "foo12bar"
    logger.warning(temp)
    assert caplog.records[0].message == "foo****bar"
    assert temp == "foo12bar"


def test_arg_multiple(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    num1 = '123'
    num2 = '4567'
    logger.warning("foo %s-%s", num1, num2)
    assert caplog.records[0].message == "foo ****-****7"
    assert num1 == '123'
    assert num2 == '4567'


def test_arg_list(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    nums = ['123', '4567']
    logger.warning("foo %s", nums)
    assert caplog.records[0].message == "foo ['****', '****7']"
    assert nums == ['123', '4567']


def test_arg_list_with_none(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    nums = [None, '4567']
    logger.warning("foo %s", nums)
    assert caplog.records[0].message == "foo [None, '****7']"
    assert nums == [None, '4567']


def test_arg_list_with_digits(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    nums = [123, '4567']
    logger.warning("foo %s", nums)
    assert caplog.records[0].message == "foo [123, '****7']"
    assert nums == [123, '4567']


def test_arg_set(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    data = {'abc123'}
    logger.warning("ids %s", data)
    arg = caplog.records[0].args[0]
    assert arg == {'abc****'}
    assert isinstance(arg, set)
    assert data == {'abc123'}  # original untouched


def test_arg_frozenset(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    logger.warning("ids %s", frozenset({'abc123'}))
    arg = caplog.records[0].args[0]
    assert arg == frozenset({'abc****'})
    assert isinstance(arg, frozenset)


def test_arg_deque(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    logger.warning("q %s", deque(['abc123', 'ok']))
    arg = caplog.records[0].args[0]
    assert arg == deque(['abc****', 'ok'])
    assert isinstance(arg, deque)


def test_arg_namedtuple_preserves_type(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    Point = namedtuple('Point', ['x', 'y'])
    logger.warning("p %s", Point('id123', 'ok'))
    arg = caplog.records[0].args[0]
    assert arg == ('id****', 'ok')
    assert isinstance(arg, Point)  # rebuilt via namedtuple._make, type preserved
    assert arg.x == 'id****'


def test_arg_set_in_extra(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    logger.warning("foo", extra={'tags': {'abc123'}})
    assert caplog.records[0].tags == {'abc****'}
    assert isinstance(caplog.records[0].tags, set)


def test_duck_typed_collection_not_iterated(caplog, logger_setup):
    # An object that only looks like a Collection (e.g. a Django QuerySet, whose
    # iteration would hit the DB) must NOT be iterated; it falls back to repr
    # redaction. We match registered Sequence/Set, not the duck-typed Collection.
    logger = logger_setup([re.compile(r'\d{3}')])

    class FakeQuerySet:
        iterated = False

        def __iter__(self):
            FakeQuerySet.iterated = True
            return iter(['secret123'])

        def __len__(self):
            return 1

        def __contains__(self, item):
            return False

        def __repr__(self):
            return 'FakeQuerySet([...])'

    logger.warning("qs %s", FakeQuerySet())
    assert FakeQuerySet.iterated is False


def test_arg_dict(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    bar = {'bar': '123'}
    logger.warning("foo %s", bar)
    assert caplog.records[0].message == "foo {'bar': '****'}"
    assert bar == {'bar': '123'}


def test_arg_dict_with_digits(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    bar = {'bar': 123}
    logger.warning("foo %s", bar)
    assert caplog.records[0].message == "foo {'bar': 123}"
    assert bar == {'bar': 123}


def test_arg_dict_with_key_to_remove(caplog, logger_setup):
    logger = logger_setup()
    dict_keys = {'phonenumber': '123', 'firstname': 'Arman'}
    logger.warning("foo %(phonenumber)s %(firstname)s", dict_keys)
    assert caplog.records[0].message == "foo **** Arman"
    assert dict_keys == {'phonenumber': '123', 'firstname': 'Arman'}


def test_arg_dict_with_none(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    bar = {'bar': None}
    logger.warning("foo %s", bar)
    assert caplog.records[0].message == "foo {'bar': None}"
    assert bar == {'bar': None}


def test_arg_nested_dict(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    bar = {
        'bar': {
            'api_key': 'key=123',
        },
    }
    logger.warning("foo %(bar)s", bar)
    assert caplog.records[0].message == "foo {'api_key': 'key=****'}"
    assert bar == {
        'bar': {
            'api_key': 'key=123',
        },
    }


def test_arg_nested_dict_with_none(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    bar = {
        'bar': {
            'api_key': None,
        },
    }
    logger.warning("foo %(bar)s", bar)
    assert caplog.records[0].message == "foo {'api_key': None}"
    assert bar == {
        'bar': {
            'api_key': None,
        },
    }


def test_extra_string_value(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    bar_extra = {'bar': '123 too'}
    logger.warning("foo", extra=bar_extra)
    assert caplog.records[0].bar == "**** too"
    assert bar_extra == {'bar': '123 too'}


def test_extra_int_value(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    bar = {'bar': 123}
    logger.warning("foo", extra=bar)
    assert caplog.records[0].bar == 123
    assert bar == {'bar': 123}


def test_extra_float_value(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    bar = {'bar': 123.6}
    logger.warning("foo", extra=bar)
    assert caplog.records[0].bar == 123.6
    assert bar == {'bar': 123.6}


def test_extra_nested_dict(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    extra_data = {
        'bar': {
            'api_key': 'key=123',
        },
    }
    logger.warning("foo", extra=extra_data)
    assert caplog.records[0].bar['api_key'] == "key=****"
    assert extra_data == {
        'bar': {
            'api_key': 'key=123',
        },
    }


def test_extra_do_redact_key(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    for mapping_type in MAPPING_TYPES:
        extra_data = mapping_type({'thing987': '123'})
        logger.warning("foo", extra=extra_data)
        assert caplog.records[0].thing987 == "****"
        assert extra_data == {'thing987': '123'}
        assert isinstance(extra_data, mapping_type)


def test_extra_do_not_redact_key(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    for mapping_type in MAPPING_TYPES:
        extra_data = mapping_type({'thing987': 'foobar'})
        logger.warning("foo", extra=extra_data)
        assert caplog.records[0].thing987 == "foobar"
        assert extra_data == {'thing987': 'foobar'}
        assert isinstance(extra_data, mapping_type)


def test_extra_nested_dict_with_list(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    for mapping_type in MAPPING_TYPES:
        extra_data = mapping_type({
            'bar': mapping_type({
                'thing': ['one', '456'],
            }),
        })
        logger.warning("foo", extra=extra_data)
        assert caplog.records[0].bar['thing'][0] == 'one'
        assert caplog.records[0].bar['thing'][1] == '****'
        assert extra_data == {
            'bar': {
                'thing': ['one', '456'],
            },
        }
        assert isinstance(extra_data, mapping_type)
        assert isinstance(extra_data['bar'], mapping_type)


def test_extra_nested_dict_with_tuple(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    for mapping_type in MAPPING_TYPES:
        extra_data = mapping_type({
            'bar': mapping_type({
                'thing': ('one', '456'),
            }),
        })
        logger.warning("foo", extra=extra_data)
        assert caplog.records[0].bar['thing'][0] == 'one'
        assert caplog.records[0].bar['thing'][1] == '****'
        assert extra_data == {
            'bar': {
                'thing': ('one', '456'),
            },
        }
        assert isinstance(extra_data, mapping_type)
        assert isinstance(extra_data['bar'], mapping_type)


def test_match_group(caplog, logger_setup):
    # Nothing in the code has to change
    # But this shows the use of a Positive Lookbehind
    # https://www.regextutorial.org/positive-and-negative-lookbehind-assertions.php
    logger = logger_setup([re.compile(r'(?<=api_key=)[\w-]+')])
    message = "example.com?api_key=this-is-my-key&sort=price"
    logger.warning(message)
    assert caplog.records[0].message == "example.com?api_key=****&sort=price"
    message = "example.com?api_key=this-is-my-key&sort=price"


def test_extra_do_redact_specific_key(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    phonenumber = {'phonenumber': 'foobar'}
    logger.warning("foo", extra=phonenumber)
    assert caplog.records[0].phonenumber == "****"
    assert phonenumber == {'phonenumber': 'foobar'}


def test_extra_with_none(caplog, logger_setup):
    logger = logger_setup([re.compile(r'\d{3}')])
    phonenumber = {'phonenumber': None}
    logger.warning("foo", extra=phonenumber)
    assert caplog.records[0].phonenumber is None
    assert phonenumber == {'phonenumber': None}


EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')


def test_arg_object_str_leak(caplog, logger_setup):
    # An object whose str() exposes data should be redacted (the reported bug)
    logger = logger_setup([EMAIL_PATTERN])

    class Foo:
        def __str__(self):
            return 'test@email.com'

    foo = Foo()
    logger.warning('test@email.com - %s', foo)
    assert caplog.records[0].message == "**** - ****"
    # The original object is untouched
    assert str(foo) == 'test@email.com'


def test_arg_object_repr_leak(caplog, logger_setup):
    # Redaction also applies when the object is rendered via repr (e.g. in a list)
    logger = logger_setup([EMAIL_PATTERN])

    class Foo:
        def __repr__(self):
            return 'Foo(test@email.com)'

    foo = Foo()
    logger.warning('%s', [foo])
    assert caplog.records[0].message == "[Foo(****)]"
    assert repr(foo) == 'Foo(test@email.com)'


def test_arg_object_non_matching_untouched(caplog, logger_setup):
    # An object whose representation has nothing to redact is left as-is
    logger = logger_setup([EMAIL_PATTERN])

    class Foo:
        def __str__(self):
            return 'nothing sensitive here'

    logger.warning('%s', Foo())
    assert caplog.records[0].message == "nothing sensitive here"


def test_arg_object_numeric_conversion_preserved(caplog, logger_setup):
    # %d uses __int__, which we never touch, so numeric formatting keeps working
    # even when the object's str() would otherwise be redacted
    logger = logger_setup([EMAIL_PATTERN])

    class Weird:
        def __int__(self):
            return 9

        def __str__(self):
            return 'test@email.com'

    logger.warning('%s is %d', Weird(), Weird())
    assert caplog.records[0].message == "**** is 9"


def test_arg_object_unredactable_left_untouched(caplog, logger_setup):
    # Objects whose __class__ can't be reassigned (e.g. __slots__ with no
    # __dict__) are left untouched rather than replaced with a string, so that
    # non-string conversions like %d keep working. Their repr is not redacted.
    logger = logger_setup([EMAIL_PATTERN])

    class Slotted:
        __slots__ = ()

        def __str__(self):
            return 'test@email.com'

    logger.warning('%s', Slotted())
    assert caplog.records[0].message == "test@email.com"


def test_arg_object_with_int_redacted(caplog, logger_setup):
    logger = logger_setup([EMAIL_PATTERN])

    class Slotted:
        __int__ = ()

        def __str__(self):
            return 'test@email.com'

    logger.warning('%s', Slotted())
    assert caplog.records[0].message == "****"


def test_arg_number_with_d_conversion_preserved(caplog, logger_setup):
    # Numbers are left untouched (not re-taggable), so %d keeps working even
    # when a pattern would otherwise match their digits.
    logger = logger_setup([re.compile(r'\d{3}')])
    logger.warning('count: %d', 1234)
    assert caplog.records[0].message == "count: 1234"


def test_arg_mapping_with_non_standard_constructor(caplog, logger_setup):
    # A mapping whose constructor doesn't take a list of (k, v) tuples (like
    # Django's QueryDict) must still be redacted in place without crashing,
    # keeping its original type.
    logger = logger_setup([EMAIL_PATTERN])
    qd = QueryDictLike('user=a@b.com&n=5')
    logger.warning('%s', qd)
    redacted = caplog.records[0].args
    assert isinstance(redacted, QueryDictLike)
    assert redacted == {'user': '****', 'n': '5'}
    assert qd == {'user': 'a@b.com', 'n': '5'}  # original untouched


@pytest.mark.skipif(not HAS_DJANGO, reason='django is not installed')
def test_arg_django_querydict(caplog, logger_setup):
    # The exact scenario from issue #14: a Django QueryDict no longer crashes
    # the filter and gets redacted.
    logger = logger_setup([EMAIL_PATTERN])
    qd = QueryDict('user=a@b.com&n=5', mutable=False)
    logger.warning('Processing %s', qd)
    message = caplog.records[0].message
    assert 'a@b.com' not in message
    assert '****' in message


def test_filter_survives_redaction_error(caplog, logger_setup):
    # A failure while redacting one field must not crash logging: the original
    # record still goes through and the error is reported on the app's logger.
    logger = logger_setup([EMAIL_PATTERN])
    logger.warning('hello %s', ExplodingMapping())  # must not raise

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings[0].getMessage().startswith('hello ')

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert errors[0].getMessage() == (
        '[loggingredactor.redacting_filter.RedactingFilter] '
        'Could not redact logs due to an error!'
    )


def test_redaction_error_reported_with_subclass_name(caplog, request):
    # The error prefix is built from the runtime class, so a subclass reports
    # under its own name rather than a hardcoded 'RedactingFilter'.
    logger = logging.getLogger(request.node.name)
    logger.addFilter(CustomRedactingFilter([EMAIL_PATTERN]))
    logger.warning('hello %s', ExplodingMapping())  # must not raise

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert errors[0].getMessage() == (
        '[%s.CustomRedactingFilter] Could not redact logs due to an error!'
        % CustomRedactingFilter.__module__
    )


def test_silent_failure_suppresses_error_log(caplog, request):
    # With silent_failure=True the redaction error is swallowed silently: the
    # original record still emits, but no error is logged.
    logger = logging.getLogger(request.node.name)
    logger.addFilter(loggingredactor.RedactingFilter([EMAIL_PATTERN], silent_failure=True))
    logger.warning('hello %s', ExplodingMapping())  # must not raise

    assert [r for r in caplog.records if r.levelno == logging.ERROR] == []
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings[0].getMessage().startswith('hello ')
