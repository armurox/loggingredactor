import re
import logging
import importlib.util

import pytest

import loggingredactor


def test_common_pii_patterns_accessible():
    from loggingredactor import common_pii_filters
    from loggingredactor.common_pii_filters import PHONE

    assert common_pii_filters.EMAIL.search('arman@example.com')
    assert PHONE.US.search('+1 415-555-2671')
    assert PHONE.AE.search('+971 50 123 4567')
    assert PHONE.INTERNATIONAL.search('+44 20 7946 0958')
    assert common_pii_filters.EMAIL in common_pii_filters.PII_PATTERNS
    assert PHONE.US in common_pii_filters.PII_PATTERNS
    assert 'US' in common_pii_filters.PHONE_PATTERNS
    assert 'password' in common_pii_filters.PII_KEYS


def test_phone_namespace_country_regexes():
    from loggingredactor.common_pii_filters import PHONE

    samples = {
        'US': '+1 415-555-2671',
        'GB': '+44 20 7946 0958',
        'DE': '+49 30 12345678',
        'FR': '+33 1 23 45 67 89',
        'IN': '+91 98765 43210',
        'AE': '+971 50 123 4567',
        'AU': '+61 2 9374 4000',
    }
    for code, number in samples.items():
        assert getattr(PHONE, code).search(number), f'{code} should match {number}'


def test_common_pii_filter_redacts_email_and_phone(caplog, request):
    logger = logging.getLogger(request.node.name)
    logger.addFilter(loggingredactor.CommonPIIRedactingFilter(mask='REDACTED'))
    logger.warning('contact %s or %s', 'arman@example.com', '+1 415-555-2671')

    message = caplog.records[0].getMessage()
    assert 'arman@example.com' not in message
    assert '+1 415-555-2671' not in message
    assert message == 'contact REDACTED or REDACTED'


def test_common_pii_filter_redacts_common_keys(caplog, request):
    logger = logging.getLogger(request.node.name)
    logger.addFilter(loggingredactor.CommonPIIRedactingFilter(mask='REDACTED'))
    logger.warning('login %(password)s', {'password': 'hunter2'})

    assert caplog.records[0].getMessage() == 'login REDACTED'


def test_common_pii_filter_combines_user_patterns_and_keys(caplog, request):
    # User-supplied patterns/keys are combined with the built-ins, not replacing
    # them: the built-in email pattern and password key still work alongside the
    # custom SECRET pattern and custom_key.
    logger = logging.getLogger(request.node.name)
    logger.addFilter(loggingredactor.CommonPIIRedactingFilter(
        [re.compile(r'SECRET-\w+')], mask='X', mask_keys={'custom_key'}))

    logger.warning('e=%s code=%s', 'a@b.com', 'SECRET-123')
    first = caplog.records[0].getMessage()
    assert 'a@b.com' not in first        # built-in email pattern
    assert 'SECRET-123' not in first     # user-supplied pattern
    assert first == 'e=X code=X'

    logger.warning('%(password)s %(custom_key)s', {'password': 'p', 'custom_key': 'c'})
    assert caplog.records[1].getMessage() == 'X X'  # built-in key + user key


@pytest.mark.skipif(importlib.util.find_spec('phonenumbers') is None,
                    reason='phonenumbers is not installed')
def test_phone_regions_use_phonenumbers_when_available(caplog, request):
    logger = logging.getLogger(request.node.name)
    logger.addFilter(loggingredactor.CommonPIIRedactingFilter(phone_regions=['US'], mask='X'))

    # a valid US number is detected and redacted...
    logger.warning('call %s', '+1 415-555-2671')
    assert caplog.records[0].getMessage() == 'call X'
    # ...but phonenumbers validates, so an impossible number is left alone
    logger.warning('id %s', '000-000-0000')
    assert caplog.records[1].getMessage() == 'id 000-000-0000'


def test_phone_regions_fall_back_to_curated_regex(caplog, request, monkeypatch):
    # With phonenumbers unavailable, the curated (looser) regex is used: it
    # matches the region's formats without validating them.
    monkeypatch.setattr('importlib.util.find_spec', lambda *_a, **_k: None)
    logger = logging.getLogger(request.node.name)
    logger.addFilter(loggingredactor.CommonPIIRedactingFilter(phone_regions=['US'], mask='X'))

    logger.warning('call %s', '+1 415-555-2671')
    assert caplog.records[0].getMessage() == 'call X'
    logger.warning('id %s', '000-000-0000')
    assert caplog.records[1].getMessage() == 'id X'  # regex matches; no validation
