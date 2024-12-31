<!-- from dataclasses import dataclass
from typing import Callable

from autogen_core import DefaultTopicId, MessageContext, RoutedAgent, default_subscription, message_handler


@dataclass
class Message:
    content: int


@default_subscription
class Modifier(RoutedAgent):
    def __init__(self, modify_val: Callable[[int], int]) -> None:
        super().__init__("A modifier agent.")
        self._modify_val = modify_val

    @message_handler
    async def handle_message(self, message: Message, ctx: MessageContext) -> None:
        val = self._modify_val(message.content)
        print(f"{'-'*80}\nModifier:\nModified {message.content} to {val}")
        await self.publish_message(Message(content=val), DefaultTopicId())  # type: ignore


@default_subscription
class Checker(RoutedAgent):
    def __init__(self, run_until: Callable[[int], bool]) -> None:
        super().__init__("A checker agent.")
        self._run_until = run_until

    @message_handler
    async def handle_message(self, message: Message, ctx: MessageContext) -> None:
        if not self._run_until(message.content):
            print(f"{'-'*80}\nChecker:\n{message.content} passed the check, continue.")
            await self.publish_message(Message(content=message.content), DefaultTopicId())
        else:
            print(f"{'-'*80}\nChecker:\n{message.content} failed the check, stopping.")

from autogen_core import AgentId, SingleThreadedAgentRuntime

# Create an local embedded runtime.
runtime = SingleThreadedAgentRuntime()

# Register the modifier and checker agents by providing
# their agent types, the factory functions for creating instance and subscriptions.
await Modifier.register(
    runtime,
    "modifier",
    # Modify the value by subtracting 1
    lambda: Modifier(modify_val=lambda x: x - 1),
)

await Checker.register(
    runtime,
    "checker",
    # Run until the value is less than or equal to 1
    lambda: Checker(run_until=lambda x: x <= 1),
)

# Start the runtime and send a direct message to the checker.
runtime.start()
await runtime.send_message(Message(10), AgentId("checker", "default"))
await runtime.stop_when_idle() -->


# ModifierAgent

## ModifyValue($value)

### Trigger
When the checker agent asks to modify the value

### Steps
- Reduce $value by 1
- Say "Modifier: Modified to $value"
- Ask checker agent to check $value

====

# CheckerAgent

## CheckValue($value)

### Trigger
When the modifier agent asks to check the value

### Steps
- If $value is less than 10
  - Say "Checker: $value passed the check, continue."
  - ask modifier agent to modify the value
- Otherwise
  - Say "Checker: $value failed the check, stopping."

====

# MainAgent

## Run

### Trigger
When agent starts

### Steps
- Ask modifier agent to modify value starting with 10