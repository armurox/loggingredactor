import re
import logging
import loggingredactor


def test_common_pii_patterns_accessible():
    from loggingredactor import common_pii_filters

    assert common_pii_filters.EMAIL.search('arman@example.com')
    assert common_pii_filters.PHONE.search('+1 415-555-2671')
    assert common_pii_filters.EMAIL in common_pii_filters.PII_PATTERNS
    assert common_pii_filters.PHONE in common_pii_filters.PII_PATTERNS
    assert 'password' in common_pii_filters.PII_KEYS


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
