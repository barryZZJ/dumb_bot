import inspect
import itertools
import re
from typing import Any, Iterable, Callable, Optional, Union, Type, overload, TypeVar

T = TypeVar('T')


class StringArgConverter:
    """
    Cast list[str] args to custom type, support optional args with format `key=val`.

    Examples:


    """
    @overload
    def __init__(self, command: str = None, **kwargs: tuple[Type[T]]):
        ...

    @overload
    def __init__(self, command: str = None, **kwargs: tuple[Type[T], Optional[Union[T, Callable[[], T]]]]):
        ...

    def __init__(self, command: str = None, **kwargs: tuple[Type[T], Optional[Union[T, Callable[[], T]]], Callable[[str], T]]):
        """Predefine the desired usage of a command. Order matters.

        Parameters
        ---
        command: str, optional
            A custom text to indicate a command, e.g. '/sub now <channel> <program> [detail]'.
            Use `self.usage` to retrieve usage of format 'Usage: `command`'

        **kwargs: tuple
            keyname indicate an argument, value should be a tuple with 1, 2, or 3 elements.
            To indicate a required arg: 1 or 2 elements should be in the tuple:
                the 1st element should be a Type[T]  e.g. (str,)
                the 2nd element should be a Callable[[str], T] that casts the actual arg to T.
                    If not provided, T(value) will be used to cast value's type.

            To indicate an optional arg: 2 or 3 elements should be in the tuple:
                the 1st element should be a Type[T]  e.g. (str,)
                the 2nd element can be:
                    T, indicates its default value, e.g. (str, 'default')
                    Callable[[],T], indicates the function to retrieve its default
                        value, which is evaluated at actual arg parsing,
                        e.g. (datetime.datetime, lambda: datetime.datetime.now())
                the 3rd element should be a Callable[[str], T] that casts the actual arg to T.
                    If not provided, T(value) will be used to cast value's type.

        """
        # TODO maybe use Pydantic
        self.text = command
        self._required_args = []
        self._optional_args = {}
        self._target_type = {}  # TODO maybe support Union?
        self._cast_funcs = {}
        for key, val in kwargs.items():
            assert isinstance(val, (tuple, list)) and 1 <= len(val) <= 3, 'kwargs should be a tuple with 1-3 elements!'
            self._target_type[key] = val[0]
            if len(val) == 1:
                self._required_args.append(key)
            elif len(val) == 2:
                if callable(val[1]):
                    param_len = len(inspect.signature(val[1]).parameters)
                    assert param_len == 0 or param_len == 1, 'the 2nd element is a function, but does not take in 1 argument (cast function for required arg) or 0 argument (default value function for optional arg)'
                    if param_len == 1:
                        # val[1] is a cast function for required arg
                        self._required_args.append(key)
                        self._cast_funcs[key] = val[1]
                        continue
                # val[1] is a default value (may be callable) for optional arg
                self._optional_args[key] = val[1]
            else:
                self._optional_args[key] = val[1]
                self._cast_funcs[key] = val[2]
        self._MIN_LEN = len(self._required_args)
        self._MAX_LEN = len(kwargs)

    @property
    def usage(self):
        return ('Usage: ' + self.text) if self.text else ''

    def check_arg_len(self, actual_args) -> bool:
        """return True if len(args) is acceptable."""
        return self._MIN_LEN <= len(actual_args) <= self._MAX_LEN

    def _default_value(self, key):
        val = self._optional_args.get(key)
        if callable(val):
            return val()
        return val

    def parse_args(self, actual_args: list[str]) -> Iterable:
        """
        Parse actual_args.

        Required args does not support key=value format,
        positional args should either in order or with format `key=value`.

        Returns:
            List of parsed argument value ordered the same as initialization.
        Note:
            Use (arg1,) to accept return value if only one arg.
        """
        parsed_args = {}

        # Parse required positional arguments
        for i, arg_name in enumerate(self._required_args):
            parsed_args[arg_name] = self._cast(actual_args[i], arg_name)

        # Parse optional keyword arguments
        foundKwargs = False
        for arg in actual_args[len(self._required_args):]:
            if '=' in arg:
                # Argument with name and value
                key, value = re.match(r'(\w+?)=(.+)', arg).group(1, 2)
                if key in parsed_args:
                    raise TypeError('多次给`' + key + '`赋值！')
                if key not in self._optional_args:
                    raise TypeError('非法参数名`' + key + '`！')
                parsed_args[key] = self._cast(value, key)
                foundKwargs = True
            elif not foundKwargs:
                # Argument without name, assign it to the next available optional argument
                for key in self._optional_args:
                    if key not in parsed_args:
                        parsed_args[key] = self._cast(arg, key)
                        break
            else:
                raise SyntaxError('名称参数后不能出现位置参数！')

        # Assign default values to any remaining optional arguments not provided
        for key in self._optional_args:
            default_value = self._default_value(key)
            if key not in parsed_args:
                parsed_args[key] = default_value

        return [parsed_args.get(key) for key in itertools.chain(self._required_args, self._optional_args.keys())]

    def _cast(self, value: str, key: str) -> Any:
        """cast `value` by cast function or directly use type(arg)(value)"""
        cast = self._cast_funcs.get(key)
        # 优先使用用户提供的cast
        if cast is not None:
            return cast(value)
        # 否则直接转换为变量定义时的类型
        return self._target_type[key](value)
