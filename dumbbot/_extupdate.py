from typing import TYPE_CHECKING, ClassVar, Optional

from telegram import Update, Message
from telegram._utils.types import JSONDict

if TYPE_CHECKING:
    from telegram import Bot, User, Chat


class ExtUpdate(Update):
    """This object represents an incoming update. Added a temp_message for chain command handing,
        message and temp_message can both be present.

       Objects of this class are comparable in terms of equality. Two objects of this class are
       considered equal, if their :attr:`update_id` is equal.


    Args:
        update_id (:obj:`int`): The update's unique identifier. Update identifiers start from a
            certain positive number and increase sequentially. This ID becomes especially handy if
            you're using Webhooks, since it allows you to ignore repeated updates or to restore the
            correct update sequence, should they get out of order. If there are no new updates for
            at least a week, then identifier of the next update will be chosen randomly instead of
            sequentially.
        message (:class:`telegram.Message`, optional): New incoming message of any kind - text,
            photo, sticker, etc.
        temp_message (:class:`telegram.Message`, optional): New incoming message for temp usage.

    Attributes:
        update_id (:obj:`int`): The update's unique identifier. Update identifiers start from a
            certain positive number and increase sequentially. This ID becomes especially handy if
            you're using Webhooks, since it allows you to ignore repeated updates or to restore the
            correct update sequence, should they get out of order. If there are no new updates for
            at least a week, then identifier of the next update will be chosen randomly instead of
            sequentially.
        message (:class:`telegram.Message`): Optional. New incoming message of any kind - text,
            photo, sticker, etc.
    """
    TEMP_MESSAGE: ClassVar[str] = 'temp_message'

    def __init__(
        self,
        update_id: int = 0,
        message: Optional[Message] = None,
        *args,
        temp_message: Optional[Message] = None,
        **kwargs,
    ):
        super().__init__(update_id, message, *args, **kwargs)

        self.set_temp_message(temp_message)

    @property
    def effective_user(self) -> Optional["User"]:
        """
        :class:`telegram.User`: The user that sent this update, no matter what kind of update this
        is. If no user is associated with this update, this gives :obj:`None`. This is the case
        if :attr:`channel_post`, :attr:`edited_channel_post` or :attr:`poll` is present.

        Example:
            * If :attr:`message` is present, this will give
              :attr:`telegram.Message.from_user`.
            * If :attr:`poll_answer` is present, this will give :attr:`telegram.PollAnswer.user`.

        """
        temp_user = self.temp_message.from_user if self.temp_message else None
        user = super().effective_user or temp_user
        self._effective_user = user
        return user

    @property
    def effective_chat(self) -> Optional["Chat"]:
        """
        :class:`telegram.Chat`: The chat that this update was sent in, no matter what kind of
        update this is.
        If no chat is associated with this update, this gives :obj:`None`.
        This is the case, if :attr:`inline_query`,
        :attr:`chosen_inline_result`, :attr:`callback_query` from inline messages,
        :attr:`shipping_query`, :attr:`pre_checkout_query`, :attr:`poll` or
        :attr:`poll_answer` is present.

        Example:
            If :attr:`message` is present, this will give :attr:`telegram.Message.chat`.

        """
        temp_chat = self.temp_message.chat if self.temp_message else None
        chat = super().effective_chat or temp_chat
        self._effective_chat = chat
        return chat

    @property
    def effective_message(self) -> Optional[Message]:
        """
        :class:`telegram.Message`: The message included in this update, no matter what kind of
            update this is. More precisely, this will be the message contained in :attr:`message`
            or :attr:`temp_message` or :obj:`None`, if
            none of those are present.

        """
        temp_message = self.temp_message
        message = super().effective_message or temp_message
        self._effective_message = message
        return message

    @classmethod
    def de_json(cls, data: Optional[JSONDict], bot: "Bot") -> Optional["Update"]:
        """See :meth:`telegram.TelegramObject.de_json`."""
        data = cls._parse_data(data)

        if not data:
            return None

        data["temp_message"] = Message.de_json(data.get("temp_message"), bot)

        return super().de_json(data=data, bot=bot)

    @classmethod
    def from_update(cls, other: Update) -> 'ExtUpdate':
        return cls(
            other.update_id,
            other.message,
            other.edited_message,
            other.channel_post,
            other.edited_channel_post,
            other.inline_query,
            other.chosen_inline_result,
            other.callback_query,
            other.shipping_query,
            other.pre_checkout_query,
            other.poll,
            other.poll_answer,
            other.my_chat_member,
            other.chat_member,
            other.chat_join_request,
        )

    def set_temp_message(self, temp_message: Message):
        with self._unfrozen():
            self.temp_message = temp_message
