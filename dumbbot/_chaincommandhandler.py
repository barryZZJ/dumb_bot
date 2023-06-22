#!/usr/bin/env python
#
# A library that provides a Python interface to the Telegram Bot API
# Copyright (C) 2015-2023
# Leandro Toledo de Souza <devs@python-telegram-bot.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser Public License for more details.
#
# You should have received a copy of the GNU Lesser Public License
# along with this program.  If not, see [http://www.gnu.org/licenses/].
"""This module contains the CommandHandler class."""
import re
from typing import TYPE_CHECKING, FrozenSet, List, Optional, Tuple, TypeVar, Union, Any

from dumbbot._extupdate import ExtUpdate
from telegram import Update, Message
from telegram.ext._handler import BaseHandler
from telegram._utils.defaultvalue import DEFAULT_TRUE
from telegram._utils.types import SCT, DVType
from telegram.ext._utils.types import UT, CCT, FilterDataDict, HandlerCallback
from telegram.ext import filters as filters_module

# from telegram import MessageEntity

if TYPE_CHECKING:
    from tgbot.telegram import Application

RT = TypeVar("RT")


class ChainCommandHandler(BaseHandler[Update, CCT]):
    """
    Add ability to chain any level of sub command handlers.
    Need to contain '/' in command explicitly.
    Arguments enclosed by double quotes won't be splitted.


    Warning:
        One and only one of the arguments between `callback` and `sub_commands` should be provided.

    Args:
        command (:obj:`str` | Collection[:obj:`str`]):
            The command or list of commands this handler should listen for. Need to contain '/' explicitly. Case-insensitive.
            Empty string matches any text, mainly used for `default` compatibility.
            Limitations are the same as for :attr:`telegram.BotCommand.command`.
        callback (:term:`function`, optional): The callback function for this handler. Will be
            called when :meth:`check_update` has determined that an update should be processed by
            this handler. Callback signature::

                def callback(update: Update, context: CallbackContext)

            The return value of the callback is usually ignored except for the special case of
            :class:`telegram.ext.ConversationHandler`.
        sub_command_handlers: (:obj:`dict[str, HandlerCallback | ChainCommandHandler]`, optional): Add optional
            sub commands, can chain more sub commands by providing ChainCommandHandler in the
            dict values.
        default (:term:`function`, optional): The default callback for when command matches but all sub commands
            are not matched.
        filters (:class:`telegram.ext.filters.BaseFilter`, optional): A filter inheriting from
            :class:`telegram.ext.filters.BaseFilter`. Standard filters can be found in
            :mod:`telegram.ext.filters`. Filters can be combined using bitwise
            operators (``&`` for :keyword:`and`, ``|`` for :keyword:`or`, ``~`` for :keyword:`not`)
        block (:obj:`bool`, optional): Determines whether the return value of the callback should
            be awaited before processing the next handler in
            :meth:`telegram.ext.Application.process_update`. Defaults to :obj:`True`.

            .. seealso:: :wiki:`Concurrency`

    Raises:
        :exc:`ValueError`: When the command is too long or has illegal chars.

    Attributes:
        commands (FrozenSet[:obj:`str`]): The set of commands this handler should listen for.
        callback (:term:`function`): The callback function for this handler.
        sub_handlers: Optional[Dict[str, Union[HandlerCallback[Update, CCT, RT], 'ChainCommandHandler']]] = None.
        default_handler: Optional['ChainCommandHandler']: The handler created by `default` callback.
        filters (:class:`telegram.ext.filters.BaseFilter`): Optional. Only allow updates with these
            Filters.
        block (:obj:`bool`): Determines whether the return value of the callback should be
            awaited before processing the next handler in
            :meth:`telegram.ext.Application.process_update`.
    """

    __slots__ = (
        "commands",
        "sub_handlers",
        "filters",
        "default_handler",
        "pat_command_part",

    )

    def __init__(
        self,
        command: SCT[str],
        callback: Optional[HandlerCallback[Update, CCT, RT]] = None,
        sub_command_handlers: Optional[List['ChainCommandHandler']] = None,
        filters: Optional[filters_module.BaseFilter] = None,
        block: DVType[bool] = DEFAULT_TRUE,
        default: Optional[HandlerCallback[Update, CCT, RT]] = None,
    ):
        super().__init__(callback, block=block)

        self.sub_handlers: Optional[List['ChainCommandHandler']] = sub_command_handlers

        if not (self._has_callback ^ self._has_sub_handler):
            raise AttributeError('One and only one of the arguments between '
                                 'callback and sub_command_handlers should be provided!')

        if default is not None and self._has_callback:
            raise AttributeError('Default should only be provided when sub_command_handlers'
                                 'are provided!')

        if isinstance(command, str):
            commands = frozenset({command.lower()})
        else:
            commands = frozenset(x.lower() for x in command)
        for comm in commands:
            if comm != '' and not re.match(r"^/?[\da-z_-]{1,32}$", comm):
                raise ValueError(f"Command `{comm}` is not a valid bot command")
            if comm == '' and filters is not None:
                raise AttributeError('filters are not supported when command is empty!')
        self.commands: FrozenSet[str] = commands
        # TODO escape \\" in text
        self.pat_command_part = r'(\S*="[^"]+"|"[^"]+"|\S+)'
        """used for splitting text into parts, basically split by space, 
        except for those (optionally start with 'key=' then) enclosed with double quotes"""

        self.default_handler = ChainCommandHandler('', default) if default else None

        self.filters: filters_module.BaseFilter = (
            filters if filters is not None else filters_module.TEXT
        )

    @property
    def _has_sub_handler(self):
        return self.sub_handlers is not None

    @property
    def _has_callback(self):
        return self.callback is not None

    def check_update(
        self, update: object
    ) -> Optional[Union[bool, Tuple[List[int], List[str], Optional[Union[bool, FilterDataDict]]]]]:
        """Determines whether an update should be passed to this handler's :attr:`callback`.

        Args:
            update (:class:`telegram.Update` | :obj:`object`): Incoming update.

        Returns:
            :obj:`list`: The list of checked sub command indices stack and the list of args for the handler.

        """
        if isinstance(update, Update) and update.effective_message:
            if not isinstance(update, ExtUpdate):
                update = ExtUpdate.from_update(update)
            message = update.temp_message or update.message  # use temp_message first for command matching
            # empty string matches every text
            if any(cmd == '' for cmd in self.commands):
                ind_stack = [-1]
                args = self.extract_args(message)
                return ind_stack, args, True

            # does not match empty text
            if not message.text:
                return None

            match_command = self.extract_command(message)  # get the first part
            if not match_command:
                return None
            command = match_command[0]

            if command.lower() not in self.commands:
                return None
            # base command matches

            if self._has_sub_handler:
                # check sub command
                body = message.text.removeprefix(command).lstrip()
                sub_message = Message(message.id, message.date, message.chat, from_user=message.from_user, text=body)
                update.set_temp_message(sub_message)

                for i, sub_handler in enumerate(self.sub_handlers):
                    check = sub_handler.check_update(update)
                    if not (check is None or check is False):  # if yes,
                        ind_stack = check[0]
                        ind_stack.append(i)  # push the index of sub handler for handle_update's reference
                        return check
                # sub command does not match
                # restore temp_message
                update.set_temp_message(message)
                if self.default_handler:
                    return self.default_handler.check_update(update)
                return False

            # handled by self (self.callback == True)
            filter_result = self.filters.check_update(update)
            if filter_result:
                ind_stack = []
                args = self.extract_args(message, match_command.end())
                return ind_stack, args, filter_result
            return False
        return None

    def handle_update(
        self,
        update: UT,
        application: "Application[CCT, Any]",
        check_result: Optional[Union[bool, Tuple[List[int], List[str], Optional[bool]]]],
        context: CCT,
    ) -> RT:
        if self._has_sub_handler:
            # handled by sub handlers
            ind_stack = check_result[0]
            ind = ind_stack.pop()
            if ind != -1:
                handler = self.sub_handlers[ind]
                return handler.handle_update(update, application, check_result, context)
            # handled by default handler
            return self.default_handler.handle_update(update, application, check_result, context)

        # handled by self
        return super(ChainCommandHandler, self).handle_update(update, application, check_result, context)

    def collect_additional_context(
        self,
        context: CCT,
        update: Update,  # skipcq: BAN-B301
        application: "Application[CCT, Any]",  # skipcq: BAN-B301
        check_result: Optional[Union[bool, Tuple[List[int], List[str], Optional[bool]]]],
    ) -> None:
        """Add text after the command to :attr:`CallbackContext.args` as list, split on single
        whitespaces and add output of data filters to :attr:`CallbackContext` as well.
        """
        if isinstance(check_result, tuple):
            context.args = check_result[1]
            if isinstance(check_result[2], dict):
                context.update(check_result[2])

    def extract_command(self, message: Message) -> re.Match:
        """
        Split text by space (skip those enclosed by double quotes) and return first part.
        """
        return re.match(self.pat_command_part, message.text)

    def extract_args(self, message: Message, pos=0) -> list[str]:
        """
        Split text by space (skip those enclosed by double quotes) and returns the list.

        Note:
            Text enclosed with double quotes won't be split.
            Text with format key="val" won't be split.
            Double quotes are stripped in the result list.

        Args:
            pos: discard the text before this position.
        """
        pat = re.compile(self.pat_command_part)
        args = pat.findall(message.text, pos=pos)
        # TODO replace might be dangerous for excessive double quote
        args = [arg.replace('"', '') for arg in args]
        return args

    def __repr__(self):
        if not self._has_sub_handler:
            return 'ChainCommandHandler([' + ', '.join("'" + cmd + "'" for cmd in self.commands) + ']' + ')'
        else:
            return 'ChainCommandHandler([' + ', '.join("'" + cmd + "'" for cmd in self.commands) + '],' + ','.join(repr(subcmdhdlr) for subcmdhdlr in self.sub_handlers) + ')'
