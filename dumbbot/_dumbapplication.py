import asyncio
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Generator,
    Optional,
    Union,
)

from telegram._update import Update
from telegram._utils.defaultvalue import DEFAULT_TRUE
from telegram._utils.logging import get_logger
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
    def add_handler(self, handler: BaseHandler[Any, CCT], group: int = DEFAULT_GROUP) -> None:
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
        """Processes an error by passing it to all error handlers registered with
        :meth:`add_error_handler`. If one of the error handlers raises
        :class:`telegram.ext.ApplicationHandlerStop`, the error will not be handled by other error
        handlers. Raising :class:`telegram.ext.ApplicationHandlerStop` also stops processing of
        the update when this method is called by :meth:`process_update`, i.e. no further handlers
        (even in other groups) will handle the update. All other exceptions raised by an error
        handler will just be logged.

        .. versionchanged:: 20.0

            * ``dispatch_error`` was renamed to :meth:`process_error`.
            * Exceptions raised by error handlers are now properly logged.
            * :class:`telegram.ext.ApplicationHandlerStop` is no longer reraised but converted into
              the return value.

        Args:
            update (:obj:`object` | :class:`telegram.Update`): The update that caused the error.
            error (:obj:`Exception`): The error that was raised.
            job (:class:`telegram.ext.Job`, optional): The job that caused the error.

                .. versionadded:: 20.0
            coroutine (:term:`coroutine function`, optional): The coroutine that caused the error.

        Returns:
            :obj:`bool`: :obj:`True`, if one of the error handlers raised
            :class:`telegram.ext.ApplicationHandlerStop`. :obj:`False`, otherwise.
        """
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
