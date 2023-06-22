from typing import (
    List,
    TypeVar,
    Union, Optional,
)

from telegram import (
    Bot,
    User,
)
from telegram._utils.defaultvalue import DEFAULT_NONE
from telegram._utils.logging import get_logger
from telegram._utils.types import JSONDict, ODVInput

BT = TypeVar("BT", bound="Bot")

class DumbBot(Bot):
    _LOGGER = get_logger(__name__, class_name="DumbBot")
    """A dumb bot that don't send any http request."""

    DEFAULT_USER = User(-1, 'Dummy', True, username='dummy')

    def __init__(self, me: Optional[User] = None):
        super().__init__('DUMB')
        with self._unfrozen():
            self.me = me or self.DEFAULT_USER

    async def _do_post(
        self,
        endpoint: str,
        data: JSONDict,
        *,
        read_timeout: ODVInput[float] = DEFAULT_NONE,
        write_timeout: ODVInput[float] = DEFAULT_NONE,
        connect_timeout: ODVInput[float] = DEFAULT_NONE,
        pool_timeout: ODVInput[float] = DEFAULT_NONE,
    ) -> Union[bool, JSONDict, List[JSONDict]]:
        # Intercept post, and respond with default result, to make it completely local.
        if endpoint == 'getMe':
            return self.me.to_dict()
        elif endpoint == 'setWebhook':
            return True
        else:
            raise NotImplementedError('requesting ' + endpoint)
