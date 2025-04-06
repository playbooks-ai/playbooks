from pathlib import Path

from playbooks.applications.agent_chat import AgentChat, AgentChatConfig
from playbooks.config import LLMConfig


def get_raw_response(chunks):
    return "".join([chunk.raw for chunk in chunks if chunk.raw])


def test_order_status_conversation_flow():
    """
    Test a conversation flow with the order_status.md playbook.

    This simulates a conversation with the following user messages:
    1. "can you get me a rufund?" - expect HandoffPlaybook to get triggered
    2. "nah, help me track an order" - expect CheckOrderStatusMain and AuthenticateUserFlow
    3. "a@abc.com 333333" - expect AuthenticateUser to get triggered
    """

    order_status_playbook_path = (
        Path(__file__).parent.parent.parent.parent / "data" / "order_status.md"
    )

    config = AgentChatConfig(
        playbooks_paths=[order_status_playbook_path],
        main_model_config=LLMConfig(),
    )

    stream = False
    steps = [
        [
            None,
            ["`Begin()`"],
        ],
        [
            "waiting for my order, where is it?",
            [
                "`CheckOrderStatusMain()`",
                '`Step["CheckOrderStatusMain:01:CND"]`',
            ],
        ],
        [
            "a@abc.com 333333",
            [
                "ValidatePin",
            ],
        ],
        [
            "2332",
            [
                "ValidatePin",
                "AuthenticateUser",
            ],
        ],
        [
            "a@abc.com 2332, but first tell me what is your refund policy",
            [
                "CustomerSupportKnowledgeLookup",
                "30 days",
            ],
        ],
    ]

    agent_chat = AgentChat(config)

    for index, step in enumerate(steps):
        user_message, rsponse_asserts = step
        if index == 0:
            response = get_raw_response(agent_chat.run(stream=stream))
        else:
            response = get_raw_response(
                agent_chat.process_user_message(user_message, stream=stream)
            )

        for assert_str in rsponse_asserts:
            assert assert_str in response
