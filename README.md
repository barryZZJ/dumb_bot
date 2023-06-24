# dumb_bot

A platform-independent bot that interacts purely based on string, utilizes [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot).

**Details:**

Since PTB (python-telegram-bot) supports listening for webhooks, simply skip the process of actual webhook registration post request, then manually post to the webhook.

**Note:**

The dumbbot has to run in the main-thread (due to the telegram bot uses get_event_loop, which only works in main thread), consider use [multiprocessing](https://docs.python.org/3.9/library/multiprocessing.html).

Use dumbbot like a server.

Hint: to expose the processed result to outside, register another _awaitable_ callback and call it inside the handler's callback. E.g.:

```python
def handler_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = ...
    await self.registered_outer_callback(result)
```

## Modifications

- Added `ChainCommandHandler`: Allow for multi-level commands like `/myapp subcommand <args>`. (It also handles single-level, so it can replace `CommandHandler`)
  - Do not split arg if enclosed with double quotes `"`.
  - Need to contain `/` at start explicitly during configuration.
  - Pass `callback` for a single-level command, pass `sub_command_handlers` for multi-level commands.
    
- Added `StringArgConverter`: Map list of string args into specific types, use this to deal with `context.args`. (One can also consider using Pydantic's Model to achieve this, which is more developed.)
  - allow parsing optional args of format `key=val`
  - allow custom cast function
  - allow default value as a function for positional arg, evaluated at actual parsing time. (useful for generating time)
  - return converted arg list (or first element if only one element). 
  
- Added `UpdateGenerator`: Manually push an update to bot.

## Usage

Mainly used existing handlers are 
[CommandHandler](https://docs.python-telegram-bot.org/en/stable/telegram.ext.commandhandler.html), 
[ConversationHandler](https://docs.python-telegram-bot.org/en/stable/telegram.ext.conversationhandler.html), 
[MessageHandler](https://docs.python-telegram-bot.org/en/stable/telegram.ext.messagehandler.html).


Callbacks should be defined with exactly these arguments: `(update: Update, context: CallbackContext)`.
- To retrieve message text: `update.effective_message.text: str`
- To retrieve arg list (CommandHandler/ChainCommandHandler): `context.args: list[str]`
- To retrieve regex filtered result: `context.match: re.Match`, `context.matches: list[re.Match]`
- Use `context.bot_data` / `context.user_data` / `context.chat_data` to retrieve data dict, it can be used to communicate with other callbacks. See [here](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Storing-bot%2C-user-and-chat-related-data).
  - By default stores in memory, use [persistence](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Making-your-bot-persistent) method to store them.
  - Note: call `context.application.mark_data_for_update_persistence` to ensure the data is stored by persistent. Also, objects need to be copyable [by defining __deepcopy__(self, memo)](https://stackoverflow.com/questions/1500718/how-to-override-the-copy-deepcopy-operations-for-a-python-object).
- More details at [doc for callbackcontext](https://docs.python-telegram-bot.org/en/stable/telegram.ext.callbackcontext.html).


UpdateGenerator: Manually push updates to application, able to push messages of different types:
- `plaintext()`: push plaintext message
- `command()`: push command message
- `automatic()`: automatic push corresponding message type based on message.text starts with `/` or not.


To save bot's data like bot_data, user_data, chat_data, conversation states, etc to local file, refer to https://github.com/python-telegram-bot/python-telegram-bot/wiki/Making-your-bot-persistent


Required packages: `httpx`, `tornado`.

### Application setup

[Example bots from telegram](https://docs.python-telegram-bot.org/en/stable/examples.html), our work keeps the same structure.

**Basic app with simple CommandHandler:**

1. setup application that registers a webhook
```python
import logging

from dumbbot import DumbBot, Update, DumbApplication
from dumbbot.ext import ApplicationBuilder, ContextTypes, CommandHandler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("received", update.effective_message.text)


if __name__ == '__main__':
    builder = ApplicationBuilder()
    builder = builder.application_class(DumbApplication)
    builder = builder.bot(DumbBot())
    application = builder.build()

    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)
    application.run_webhook(port=10888)

```

2. Use UpdateGenerator to manually push update via webhook (need to run in a separate thread)
```python
import datetime
from dumbbot import UpdateGenerator, Chat, User, Message

chat = Chat(0, Chat.PRIVATE)
user = User(0, 'dummy', False, username='dummyuser')
msg = Message(0, datetime.datetime.now(), chat, from_user=user, text='/start')

generator = UpdateGenerator(port=10888)
succ = generator.command(msg)  # post update to webhook
print(succ)
```

**Note:** By default, only the first matched handler is used. To enable multiple handlers, use `group` in `application.add_handler`. See [doc here](https://docs.python-telegram-bot.org/en/stable/telegram.ext.application.html#telegram.ext.Application.add_handler).

### Use ChainCommandHandler

single-level ChainCommandHandler:

```python
from dumbbot import ChainCommandHandler, Update
from dumbbot.ext import ContextTypes

async def set_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'You are a {context.args[0]}.')

one_level_handler = ChainCommandHandler('/set-gender', callback=set_gender)
```

multi-level ChainCommandHandler:

```python
from dumbbot import Update, ChainCommandHandler
from dumbbot.ext import ContextTypes

async def git_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /git help <args>
    print('function: git_help')
    print('args:', str(context.args))

async def git_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /git add <args>
    print('function: git_add')
    print('args:', str(context.args))

async def git_remote_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /git remote help <args>
    print('function: git_remote_help')
    print('args:', str(context.args))

async def git_remote_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /git remote add <args>
    print('function: git_remote_add')
    print('args:', str(context.args))

multilevel_handler = ChainCommandHandler(
    '/git',
    sub_command_handlers=[
        ChainCommandHandler('add', git_add),
        ChainCommandHandler(
            'remote',
            sub_command_handlers=[
                ChainCommandHandler('add', git_remote_add)
            ],
            default=git_remote_help
        )
    ],
    default=git_help
)
```

ChainCommandHandler is also compatible with ConversationHandler. 

### JobQueue

Allows scheduled jobs, require `pip install apscheduler`.

See [JobQueue](https://docs.python-telegram-bot.org/en/stable/telegram.ext.jobqueue.html)


### StringArgConverter

Use this to deal with `context.args`.

See `_stringargconverter.py`

```python
import datetime
from dumbbot import StringArgConverter

def cast_ints(value: str) -> tuple[int, ...]:
    """value: single int, or int separated by ','"""
    return tuple(map(int, value.replace(' ', '').split(',')))

def cast_time(value: str) -> datetime.time:
    # format: HHMMSS or HHMM
    try:
        # raise ValueError for wrong format
        return datetime.datetime.strptime(value, '%H%M').time()
    except ValueError:
        # raise ValueError for wrong format
        return datetime.datetime.strptime(value, '%H%M%S').time()

usage = StringArgConverter(
            '/sub daily <channel> <program> <ids>'
            '[excludeProgram] [detail] [checkTime] [days] [startTime] - 添加每日定时检查任务',
            # required args
            channel=(str,),
            program=(str,),
            # required args with custom cast function
            ids=(list[int], cast_ints),
            # positional args (need default value)
            excludeProgram=(str, None),
            detail=(str, '*'),
            # positional args with default value function evaluated at parsing, and custom cast function
            checkTime=(datetime.time, lambda: datetime.datetime.now().time(), cast_time),
            # positional args with default value and custom cast function
            days=(tuple[int],
                  tuple(range(0, 6+1)),
                  cast_ints),
            startTime=(datetime.time, None, cast_time),
        )
args = ['channel_name', '"program name with space"', '1,2,3', '"optional arg without key"', 'detail="optional arg with key"', 'days=3,4,5']
if not usage.check_arg_len(args):
    print(usage.usage)
    # Usage: /sub daily <channel> <program> <ids> [excludeProgram] [detail] [checkTime] [days] [startTime] - 添加每日定时检查任务
else:
    try:
        channel, program, ids, \
        excludeProgram, detail, checkTime, days, startTime = usage.parse_args(args)
        # parsed result:
        # channel: channel_name
        # program: program name with space
        # ids: [1,2,3]
        # excludeProgram: optional arg without key
        # detail: optional arg with key
        # checkTime: <datetime.time object>
        # days: [3,4,5]
        # startTime: <datetime.time object>
    except (SyntaxError, TypeError, ValueError) as e:
        print('参数错误！')
```
