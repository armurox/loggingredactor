import re
import copy
import logging

import pytest
from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule

from loggingredactor import RedactingFilter, CommonPIIRedactingFilter


# Arbitrary values that could end up in a log record: scalars nested inside any
# of the containers the filters know how to recurse into.
_atoms = (
    st.none() | st.booleans() | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False) | st.text()
)
LOGGABLE = st.recursive(
    _atoms,
    lambda children: (
        st.lists(children)
        | st.lists(children).map(tuple)
        | st.dictionaries(st.text() | st.integers(), children)
        | st.sets(_atoms)
        | st.frozensets(_atoms)
    ),
    max_leaves=15,
)

# The properties must hold for every filter, configured to actually redact.
FILTERS = [
    pytest.param(
        lambda: RedactingFilter([re.compile(r'\d+')], mask='X',
                                mask_keys={'password'}, silent_failure=True),
        id='RedactingFilter',
    ),
    pytest.param(
        lambda: CommonPIIRedactingFilter(mask='X', mask_keys={'password'},
                                         silent_failure=True),
        id='CommonPIIRedactingFilter',
    ),
]


def _record(value):
    return logging.LogRecord('t', logging.INFO, 'p.py', 1, 'm %s', (value,), None)


@pytest.mark.parametrize('make_filter', FILTERS)
@settings(deadline=None, max_examples=200)
@given(value=LOGGABLE)
def test_filter_never_mutates_original(make_filter, value):
    snapshot = copy.deepcopy(value)
    make_filter().filter(_record(value))
    assert value == snapshot


@pytest.mark.parametrize('make_filter', FILTERS)
@settings(deadline=None, max_examples=200)
@given(value=LOGGABLE)
def test_filter_never_raises(make_filter, value):
    # Redaction errors must be swallowed: filtering always succeeds.
    assert make_filter().filter(_record(value)) is True


class _Leaky:
    """A custom object whose repr leaks data, to exercise the repr/_make path."""

    def __init__(self, n):
        self.n = n

    def __repr__(self):
        return 'Leaky(secret%s)' % self.n


class RedactionStateMachine(RuleBasedStateMachine):
    """Drive one filter instance through a sequence of records (exercising the
    subclass cache and any other per-instance state) and assert the invariants
    hold at every step."""

    def __init__(self):
        super().__init__()
        self.filter = RedactingFilter([re.compile(r'\d+')], mask='X', silent_failure=True)

    @rule(value=LOGGABLE)
    def log_value(self, value):
        snapshot = copy.deepcopy(value)
        assert self.filter.filter(_record(value)) is True
        assert value == snapshot

    @rule(n=st.integers())
    def log_custom_object(self, n):
        obj = _Leaky(n)
        assert self.filter.filter(_record(obj)) is True
        assert repr(obj) == 'Leaky(secret%s)' % n  # original left untouched


TestRedactionStateMachine = RedactionStateMachine.TestCase
TestRedactionStateMachine.settings = settings(deadline=None, max_examples=25)
