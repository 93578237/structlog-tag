from __future__ import annotations

import json
import logging
import logging.config
from io import StringIO

import pytest
import structlog
from inline_snapshot import snapshot

from structlog_tag import make_tagged_bound_logger


def configure_test_logging(
    *,
    tags: tuple[str, ...] = (),
) -> StringIO:
    stream = StringIO()
    wrapper_class = make_tagged_bound_logger(tags)

    shared_pre_chain: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    logging.config.dictConfig(
        {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'json': {
                    '()': structlog.stdlib.ProcessorFormatter,
                    'processor': structlog.processors.JSONRenderer(),
                    'foreign_pre_chain': shared_pre_chain,
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'stream': stream,
                    'formatter': 'json',
                }
            },
            'root': {'handlers': ['console'], 'level': 'WARNING'},
            'loggers': {
                'tests': {
                    'handlers': ['console'],
                    'level': 'INFO',
                    'propagate': False,
                }
            },
        }
    )

    structlog.configure(
        processors=[
            *shared_pre_chain,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=wrapper_class,
        cache_logger_on_first_use=True,
    )

    return stream


def test_filter_tags() -> None:
    stream = configure_test_logging(tags=('db',))

    result = (
        structlog.get_logger(__name__).tag('network').info('hello world', foo='bar')
    )

    assert result is None
    assert not stream.getvalue()


def test_filter_out_unknown_tags() -> None:
    stream = configure_test_logging(tags=('db',))

    result = structlog.get_logger(__name__).tag('missing').info('missing tag')

    assert result is None
    assert not stream.getvalue()


def test_empty_tags() -> None:
    stream = configure_test_logging()

    structlog.get_logger(__name__).tag('missing', 'other').info('missing tag')

    event = json.loads(stream.getvalue())
    assert event == snapshot(
        {
            'event': 'missing tag',
            'tags': ['missing', 'other'],
            'logger': __name__,
            'level': 'info',
        }
    )


def test_multiple_tags_order() -> None:
    stream = configure_test_logging(tags=('first', 'second'))

    structlog.get_logger(__name__).tag('first', 'second').info('hello world', foo='bar')

    event = json.loads(stream.getvalue())
    assert event == snapshot(
        {
            'event': 'hello world',
            'foo': 'bar',
            'tags': ['first', 'second'],
            'logger': __name__,
            'level': 'info',
        }
    )


def test_ignore_duplicated_tags() -> None:
    stream = configure_test_logging(tags=('db', 'db'))

    structlog.get_logger(__name__).tag('db').tag('db').info('hello world')

    event = json.loads(stream.getvalue())
    assert event == snapshot(
        {
            'event': 'hello world',
            'tags': ['db'],
            'logger': __name__,
            'level': 'info',
        }
    )


def test_tag_requires_at_least_one_tag() -> None:
    configure_test_logging()

    with pytest.raises(ValueError, match='at least one tag'):
        structlog.get_logger(__name__).tag()


def test_not_tagged_logging() -> None:
    stream = configure_test_logging(tags=('db',))

    app_log = structlog.get_logger(__name__)
    app_log.tag('db').error('hello world', foo='bar')

    third_party_logger = logging.getLogger('thirdparty')
    third_party_logger.debug('debug should be filtered')
    third_party_logger.warning('warning should remain')

    rendered_events = [
        json.loads(line) for line in stream.getvalue().splitlines() if line.strip()
    ]

    assert rendered_events == snapshot(
        [
            {
                'foo': 'bar',
                'level': 'error',
                'tags': ['db'],
                'event': 'hello world',
                'logger': __name__,
            },
            {
                'event': 'warning should remain',
                'logger': 'thirdparty',
                'level': 'warning',
            },
        ]
    )


def test_bind_and_unbind_preserve_context() -> None:
    stream = configure_test_logging(tags=('db',))

    log = structlog.get_logger(__name__).bind(request_id='req-1').tag('db')
    log.info('bound context')
    log.unbind('request_id').info('without request id')
    log.bind(user_id='user-1').try_unbind('missing').info('with user id')

    reset_log = structlog.get_logger(__name__).bind(request_id='stale').tag('db')
    reset_log.new(request_id='fresh').info('after new')

    rendered_events = [
        json.loads(line) for line in stream.getvalue().splitlines() if line.strip()
    ]

    assert rendered_events == snapshot(
        [
            {
                'event': 'bound context',
                'request_id': 'req-1',
                'tags': ['db'],
                'logger': __name__,
                'level': 'info',
            },
            {
                'event': 'without request id',
                'tags': ['db'],
                'logger': __name__,
                'level': 'info',
            },
            {
                'event': 'with user id',
                'request_id': 'req-1',
                'user_id': 'user-1',
                'tags': ['db'],
                'logger': __name__,
                'level': 'info',
            },
            {
                'event': 'after new',
                'request_id': 'fresh',
                'tags': ['db'],
                'logger': __name__,
                'level': 'info',
            },
        ]
    )
