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

    # redefine pickling behaviour
    def __copy__(self):
        new_object = self.__class__()
        new_object.me = self.me
        new_object._token = self._token
        new_object._bot_user = self._bot_user
        return new_object

    def __reduce__(self):
        return self.__class__, (self.me,)

    def __deepcopy__(self, memo):
        new_object = self.__class__()
        new_object.me = self.me.__deepcopy__(memo)
        new_object._token = self._token
        new_object._bot_user = self._bot_user.__deepcopy__(memo)
        return new_object

    def __getstate__(self):
        # Define what gets pickled (object's state)
        state = {k: self.__dict__[k] for k in ['_token', 'me', '_bot_user']}
        return state

    def __setstate__(self, state):
        # Restore the object's state from the unpickled dictionary
        self.__dict__.update(state)

