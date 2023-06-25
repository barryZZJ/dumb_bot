import asyncio
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Generator,
    List,
    Optional,
    Sequence,
    Union,
)

from telegram._update import Update
from telegram._utils.defaultvalue import DEFAULT_NONE, DEFAULT_TRUE
from telegram._utils.logging import get_logger
from telegram._utils.types import ODVInput
from telegram._utils.warnings import warn
from telegram.ext._application import DEFAULT_GROUP, ApplicationHandlerStop, Application
from telegram.ext._extbot import ExtBot
from telegram.ext._handler import BaseHandler
from telegram.ext._utils.types import CCT, RT

if TYPE_CHECKING:
    from telegram.ext import ConversationHandler
    from telegram.ext._jobqueue import Job

_LOGGER = get_logger(__name__)


class DumbApplication(Application):
    """Reimplement methods to avoid isinstance return False"""

    __slots__ = ('_loop',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(
        self,
        listen: str = "127.0.0.1",
        port: int = 80,
        url_path: str = "",
        cert: Optional[Union[str, Path]] = None,
        key: Optional[Union[str, Path]] = None,
        bootstrap_retries: int = 0,
        webhook_url: Optional[str] = None,
        allowed_updates: Optional[List[str]] = None,
        drop_pending_updates: Optional[bool] = None,
        ip_address: Optional[str] = None,
        max_connections: int = 40,
        close_loop: bool = True,
        stop_signals: ODVInput[Sequence[int]] = DEFAULT_NONE,
        secret_token: Optional[str] = None,
    ) -> None:
        return self.run_webhook(
            listen=listen,
            port=port,
            url_path=url_path,
            cert=cert,
            key=key,
            bootstrap_retries=bootstrap_retries,
            webhook_url=webhook_url,
            allowed_updates=allowed_updates,
            drop_pending_updates=drop_pending_updates,
            ip_address=ip_address,
            max_connections=max_connections,
            close_loop=close_loop,
            stop_signals=stop_signals,
            secret_token=secret_token,
        )

    def add_handler(self, handler: BaseHandler[Any, CCT], group: int = DEFAULT_GROUP) -> None:
        """Need this to resolve some isinstance compare issues."""
        from telegram.ext._conversationhandler import ConversationHandler

        if not isinstance(handler, BaseHandler):
            raise TypeError(f"handler is not an instance of {BaseHandler.__name__}")
        if not isinstance(group, int):
            raise TypeError("group is not int")
        if isinstance(handler, ConversationHandler) and handler.persistent and handler.name:
            if not self.persistence:
                raise ValueError(
                    f"ConversationHandler {handler.name} "
                    f"can not be persistent if application has no persistence"
                )
            if self._initialized:
                self.create_task(self._add_ch_to_persistence(handler))
                warn(
                    "A persistent `ConversationHandler` was passed to `add_handler`, "
                    "after `Application.initialize` was called. This is discouraged."
                    "See the docs of `Application.add_handler` for details.",
                    stacklevel=2,
                )

        if group not in self.handlers:
            self.handlers[group] = []
            self.handlers = dict(sorted(self.handlers.items()))  # lower -> higher groups

        self.handlers[group].append(handler)

    def _mark_for_persistence_update(
        self, *, update: Optional[object] = None, job: Optional["Job"] = None
    ) -> None:
        """Need this to resolve some isinstance compare issues."""
        if isinstance(update, Update):
            if update.effective_chat:
                self._chat_ids_to_be_updated_in_persistence.add(update.effective_chat.id)
            if update.effective_user:
                self._user_ids_to_be_updated_in_persistence.add(update.effective_user.id)

        if job:
            if job.chat_id:
                self._chat_ids_to_be_updated_in_persistence.add(job.chat_id)
            if job.user_id:
                self._user_ids_to_be_updated_in_persistence.add(job.user_id)

    async def process_error(
        self,
        update: Optional[object],
        error: Exception,
        job: Optional["Job[CCT]"] = None,
        coroutine: Optional[
            Union[Generator[Optional["asyncio.Future[object]"], None, RT], Awaitable[RT]]
        ] = None,
    ) -> bool:
        """Need this to resolve some isinstance compare issues."""
        if self.error_handlers:
            for (
                callback,
                block,
            ) in self.error_handlers.items():
                context = self.context_types.context.from_error(
                    update=update,
                    error=error,
                    application=self,
                    job=job,
                    coroutine=coroutine,
                )
                if not block or (  # If error handler has `block=False`, create a Task to run cb
                    block is DEFAULT_TRUE
                    and isinstance(self.bot, ExtBot)
                    and self.bot.defaults
                    and not self.bot.defaults.block
                ):
                    self.__create_task(
                        callback(update, context), update=update, is_error_handler=True
                    )
                else:
                    try:
                        await callback(update, context)
                    except ApplicationHandlerStop:
                        return True
                    except Exception as exc:
                        _LOGGER.exception(
                            "An error was raised and an uncaught error was raised while "
                            "handling the error with an error_handler.",
                            exc_info=exc,
                        )
            return False

        _LOGGER.exception("No error handlers are registered, logging exception.", exc_info=error)
        return False
