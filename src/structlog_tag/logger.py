from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Self, override

from structlog.stdlib import BoundLogger

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from structlog.typing import Context, Processor, WrappedLogger


class TaggedBoundLogger(BoundLogger):
    tag_bits: ClassVar[dict[str, int]]

    def __init__(
        self,
        logger: WrappedLogger,
        processors: Iterable[Processor],
        context: Context,
        *,
        tag_mask: int = 0,
        tag_names: tuple[str, ...] = (),
    ) -> None:
        super().__init__(logger, processors, context)
        self._tag_mask = tag_mask
        self._tag_names = tag_names

    def _clone(
        self,
        *,
        context: dict[str, Any] | None = None,
        tag_mask: int | None = None,
        tag_names: tuple[str, ...] | None = None,
    ) -> Self:
        return self.__class__(
            self._logger,
            self._processors,
            self._context if context is None else context,
            tag_mask=self._tag_mask if tag_mask is None else tag_mask,
            tag_names=self._tag_names if tag_names is None else tag_names,
        )

    @override
    def _proxy_to_logger(
        self,
        method_name: str,
        event: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if not self._tag_names:
            return None

        return super()._proxy_to_logger(
            method_name,
            event,
            *args,
            tags=list(self._tag_names),
            **kwargs,
        )

    @override
    def bind(self, **new_values: Any) -> Self:
        return self._clone(context=self._context.__class__(self._context, **new_values))

    def tag(self, *tags: str) -> Self:
        if not tags:
            msg = 'tag() requires at least one tag'
            raise ValueError(msg)

        if not self.tag_bits:
            return self._clone(tag_names=tuple(dict.fromkeys(tags)))

        logger = self
        for tag in tags:
            tag_bit = self.tag_bits.get(tag)
            if tag_bit is None or logger._tag_mask & tag_bit:
                continue
            logger = logger._clone(
                tag_mask=logger._tag_mask | tag_bit,
                tag_names=(*logger._tag_names, tag),
            )
        return logger


def make_tagged_bound_logger(tags: Sequence[str]) -> type[TaggedBoundLogger]:
    tag_bits: dict[str, int] = {}
    for tag in tags:
        if tag in tag_bits:
            continue
        tag_bits[tag] = 1 << len(tag_bits)

    return type(
        'TaggedBoundLoggerConfigured',
        (TaggedBoundLogger,),
        {
            'tag_bits': tag_bits,
        },
    )
