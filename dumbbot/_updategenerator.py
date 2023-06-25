# Generator Update manually
import random
import requests

from dumbbot import Update, Message, MessageEntity


def utf16len(text: str) -> int:
    return len(text.encode('utf-16-le'))


def _set_message_entity(message: Message, entities: list[MessageEntity]):
    with message._unfrozen():
        message.entities = entities


class UpdateGenerator:
    _UPDATE_ID_MAX = 100000

    def __init__(self, listen: str = "127.0.0.1", port: int = 18888):
        self._url = f'http://{listen}:{port}'
        print('ready to post to', self._url)
        self._curr_update_id = random.randint(0, self._UPDATE_ID_MAX)

    def _next_update_id(self) -> int:
        self._curr_update_id = (self._curr_update_id + 1) % self._UPDATE_ID_MAX
        return self._curr_update_id

    def _normal(self, message: Message) -> bool:
        update = Update(self._next_update_id(), message)
        print('posting', update.to_json())
        resp = requests.post(self._url, json=update.to_dict())
        return resp.ok

    def plaintext(self, message: Message) -> bool:
        """Post plaintext."""
        return self._normal(message)

    def command(self, message: Message) -> bool:
        """Post command.

        Add entity 'BOT_COMMAND' to message. text format example: '/start' or '/start@jobs_bot'"""
        entity = MessageEntity(
            MessageEntity.BOT_COMMAND,
            0,
            utf16len(message.text)
        )
        _set_message_entity(message, [entity])
        return self._normal(message)

    def automatic(self, message: Message) -> bool:
        """Post any message, automatic determine if message is plaintext or command.
        Message is considered a command if text starts with '/', if not, use `self.command(message)` manually.
        """
        if message.text.startswith('/'):
            return self.command(message)
        return self.plaintext(message)
