"""Built-in playbooks for common agent operations.

This module provides standard playbooks that are automatically available
to all agents, including messaging, artifact handling, and system operations.
"""

from playbooks.compilation.compiler import Compiler
from playbooks.compilation.markdown_to_ast import markdown_to_ast
from playbooks.utils.llm_config import LLMConfig


class BuiltinPlaybooks:
    """Provides built-in playbooks that are automatically added to every agent."""

    @staticmethod
    def get_ast_nodes():
        """Get AST nodes for built-in playbooks.

        Returns:
            List of AST nodes representing built-in playbooks.
        """
        return (
            BuiltinPlaybooks.get_python_playbooks_ast_nodes()
            + BuiltinPlaybooks.get_llm_playbooks_ast_nodes()
        )

    @staticmethod
    def get_python_playbooks_ast_nodes():
        """Get AST nodes for built-in python playbooks.

        Returns:
            List of AST nodes representing built-in python playbooks.
        """
        code_block = '''
```python
from playbooks.llm.messages.types import ArtifactLLMMessage
from playbooks.state.variables import Artifact

@playbook(hidden=True)
async def SendMessage(target_agent_id: str, message: str):
    await agent.SendMessage(target_agent_id, message)

@playbook(hidden=True)
async def WaitForMessage(source_agent_id: str) -> list:
    return await agent.WaitForMessage(source_agent_id)

@playbook
async def Say(target: str, message: str):
    await agent.Say(target, message)

@playbook
async def CreateAgent(agent_klass: str, **kwargs):
    new_agent = await agent.program.create_agent(agent_klass, **kwargs)
    await agent.program.runtime.start_agent(new_agent)
    return new_agent
    
@playbook(description="If an artifact was previously created, but is no longer available, use this Playbook to load its contents")
async def LoadArtifact(artifact_name: str):
    # Load artifact from variables
    agent.load_artifact(artifact_name)

@playbook
async def SaveArtifact(name: str, summary: str, value: str):
    artifact = Artifact(name, summary, value)
    agent.state.variables[name] = artifact
    return artifact.name

@playbook
async def InviteToMeeting(meeting_id: str, attendees: list):
    """Invite additional agents to an existing meeting."""
    return await agent.meeting_manager.InviteToMeeting(meeting_id, attendees)

@playbook
async def Loadfile(file_path: str, inline: bool = False, silent: bool = False):
    return await agent.load_file(file_path, inline, silent)

# @playbook(hidden=True)
# async def SetVar(name: str, value):
#     """Set a variable in the agent's state and return the value."""
#     if not name.startswith("$"):
#         name = f"${name}"
#     agent.state.variables[name] = value
#     return value

@playbook
async def EndProgram():
    await agent.program.end_program()

@playbook(hidden=True)
async def MessageProcessingEventLoop():
    """Main message processing loop for agents. Delegates to agent's message_processing_event_loop method."""
    await agent.message_processing_event_loop()

```        
'''

        return markdown_to_ast(code_block)["children"]

    @staticmethod
    def get_llm_playbooks_markdown():
        return """
# BuiltinPlaybooks
## ResolveDescriptionPlaceholders($playbook_call: str, $description: str) -> str
Resolves natural language placeholders as Python expressions in provided playbook description in the context of the provided playbook call
hidden: true

### Steps
- Provided $description contains contains some placeholders in {} in Python f-string syntax
- Go through each placeholder $expression
- If $expression is not valid Python syntax and is a natural language instruction
    - Attempt to convert it to valid Python syntax. If ambiguous or not known how to convert, leave it as is.
- Return description with any converted placeholders. No other changes to description allowed.

## ProcessMessages($messages: list)
hidden: true

### Steps
- For each $message in $messages
    - If $message is a MEETING_INVITATION (check if message contains "[MEETING_INVITATION for meeting" text)
        - Extract the meeting_id from the message (e.g., from "[MEETING_INVITATION for meeting 123456]")
        - Extract the inviter agent id from the message sender_id
        - Look at the topic (message content) and determine if there is a suitable meeting playbook to handle it
        - If a suitable meeting playbook is found
            - Say to the inviter that the invitation has been accepted
            - Call the meeting playbook directly: <MeetingPlaybookName>(meeting_id=<extracted_meeting_id>, inviter_id=<extracted_inviter_id>, topic=<message_content>)
            - Continue to next message
        - Otherwise
            - Reject the invitation by saying to the inviter that no suitable meeting playbook was found
            - Continue to next message
    - If $message sent to a meeting we have joined
        - Find a suitable meeting playbook if not already in one
        - If meeting playbook is found and not already running
            - Call the meeting playbook directly with meeting context
            - Continue
        - Otherwise
            - Return "No suitable meeting playbook found"
    - Analyze message content and current state and check available triggers to determine if any playbook should be triggered based on
    - If any playbook should be triggered
        - Set $_busy = True, output an appropriate trig? line and execute the playbook
        - Look at $message and the result of the playbook execution. If the message sender is expecting a response, enqueue a Say(message sender, result of the playbook execution) call
        - If the message sender is expecting a response
        - Enqueue a Say(message sender, result of the playbook execution) call
    - If no playbook is triggered but the message requires a response
        - Formulate an appropriate response based on agent's role and description
        - Enqueue a Say(message sender, response) call
"""

    @staticmethod
    def get_llm_playbooks_ast_nodes():
        markdown = BuiltinPlaybooks.get_llm_playbooks_markdown()
        llm_config = LLMConfig()
        compiler = Compiler(llm_config)

        # Compile the playbooks content
        _, compiled_content, compiled_file_path = compiler.compile(content=markdown)

        # Parse the compiled content to extract steps
        ast = markdown_to_ast(compiled_content, source_file_path=compiled_file_path)
        h1 = list(filter(lambda node: node.get("type") == "h1", ast.get("children")))[0]
        if not h1.get("type") == "h1":
            raise Exception("Expected a single h1 child")

        # filter h1 children for h2 nodes
        h2s = list(filter(lambda node: node.get("type") == "h2", h1.get("children")))
        return h2s
