"""Built-in playbooks for common agent operations.

This module provides standard playbooks that are automatically available
to all agents, including messaging, artifact handling, and system operations.
"""

from playbooks.compilation.compiler import Compiler
from playbooks.compilation.markdown_to_ast import markdown_to_ast


class BuiltinPlaybooks:
    """Provides built-in playbooks that are automatically added to every agent."""

    @staticmethod
    async def get_ast_nodes():
        """Get AST nodes for built-in playbooks.

        Returns:
            List of AST nodes representing built-in playbooks.
        """
        llm_playbooks = await BuiltinPlaybooks.get_llm_playbooks_ast_nodes()
        return BuiltinPlaybooks.get_python_playbooks_ast_nodes() + llm_playbooks

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
    await self.SendMessage(target_agent_id, message)

@playbook(hidden=True)
async def WaitForMessage(source_agent_id: str) -> list:
    return await self.WaitForMessage(source_agent_id)

@playbook
async def Say(target: str, message: str):
    await self.say(target, message)

@playbook
async def CreateAgent(agent_klass: str, **kwargs):
    new_agent = await self.program.create_agent(agent_klass, **kwargs)
    await self.program.runtime.start_agent(new_agent)
    return new_agent
    
@playbook(description="If an artifact was previously created, but is no longer available, use this Playbook to load its contents")
async def LoadArtifact(artifact_name: str):
    # Load artifact from variables
    self.load_artifact(artifact_name)

@playbook
async def SaveArtifact(name: str, summary: str, value: str):
    artifact = Artifact(name, summary, value)
    self.state[name] = artifact
    return artifact.name

@playbook
async def InviteToMeeting(meeting_id: str, attendees: list):
    """Invite additional agents to an existing meeting."""
    return await self.meeting_manager.InviteToMeeting(meeting_id, attendees)

@playbook
async def Loadfile(file_path: str, inline: bool = False, silent: bool = False):
    return await self.load_file(file_path, inline, silent)

# @playbook(hidden=True)
# async def SetVar(name: str, value):
#     """Set a variable in the agent's state and return the value."""
#     if not name.startswith("$"):
#         name = f"${name}"
#     self.state[name] = value
#     return value

@playbook
async def EndProgram():
    await self.program.end_program()

@playbook(hidden=True)
async def MessageProcessingEventLoop():
    """Main message processing loop for agents. Delegates to agent's message_processing_event_loop method."""
    await self.message_processing_event_loop()

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
    - If $message was sent to a meeting we have joined
        - This means we haven't started the meeting playbook yet. Try to find the appropriate meeting playbook using meeting topic.
        - If a suitable meeting playbook is found
            - Set $_busy = True, output an appropriate trig? line and start the meeting playbook: <MeetingPlaybookName>(meeting_id=<extracted_meeting_id>, inviter_id=<extracted_inviter_id>, topic=<message_content>)
            - Return the result of the meeting playbook execution
        - Otherwise
            - Return an error message that no suitable meeting playbook was found
            - Continue to next message
    - Analyze message content and current state and check available triggers to determine if any playbook should be triggered
    - If any playbook should be triggered
        - Set $_busy = True, output an appropriate trig? line and execute the playbook
        - Look at $message and the result of the playbook execution. If the message sender is expecting a response, enqueue a Say(message sender, result of the playbook execution) call
        - Return the result of the playbook execution
    - If no playbook was triggered but the message requires a response
        - Formulate an appropriate response based on agent's role and description
        - Enqueue a Say(message sender, response) call
"""

    @staticmethod
    async def get_llm_playbooks_ast_nodes():
        markdown = BuiltinPlaybooks.get_llm_playbooks_markdown()
        compiler = Compiler()

        # Compile the playbooks content
        _, compiled_content, compiled_file_path = await compiler.compile(
            content=markdown
        )

        # Parse the compiled content to extract steps
        ast = markdown_to_ast(compiled_content, source_file_path=compiled_file_path)
        h1 = list(filter(lambda node: node.get("type") == "h1", ast.get("children")))[0]
        if not h1.get("type") == "h1":
            raise Exception("Expected a single h1 child")

        # filter h1 children for h2 nodes
        h2s = list(filter(lambda node: node.get("type") == "h2", h1.get("children")))
        return h2s
