from playbooks.utils.markdown_to_ast import markdown_to_ast

from ..compiler import Compiler
from ..utils.llm_config import LLMConfig


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
from playbooks.utils.spec_utils import SpecUtils

@playbook(hidden=True)
async def SendMessage(target_agent_id: str, message: str):
    await agent.SendMessage(target_agent_id, message)

@playbook(hidden=True)
async def WaitForMessage(source_agent_id: str) -> str | None:
    return await agent.WaitForMessage(source_agent_id)

@playbook
async def Say(target: str, message: str):
    await agent.Say(target, message)

@playbook
async def CreateAgent(agent_klass: str, **kwargs):
    new_agent = await agent.program.create_agent(agent_klass, **kwargs)
    await agent.program.runtime.start_agent(new_agent)
    return new_agent
    
@playbook
async def SaveArtifact(artifact_name: str, artifact_summary: str, artifact_content: str):
    agent.state.artifacts.set(artifact_name, artifact_summary, artifact_content)

@playbook
async def LoadArtifact(artifact_name: str):
    return agent.state.artifacts[artifact_name]

@playbook
async def InviteToMeeting(meeting_id: str, attendees: list):
    """Invite additional agents to an existing meeting."""
    return await agent.invite_to_meeting(meeting_id, attendees)

@playbook
async def Loadfile(file_path: str, inline: bool = False, silent: bool = False):
    return await agent.load_file(file_path, inline, silent)

@playbook(hidden=True)
async def SetVar(name: str, value):
    """Set a variable in the agent's state and return the value."""
    if not name.startswith("$"):
        name = f"${name}"
    agent.state.variables[name] = value
    return value

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

## MessageProcessingEventLoop
hidden: true

### Steps
- Loop forever
    - Set $_busy = False
    - WaitForMessage("*")
    - Here we will decide if any playbook should be triggered. Carefully consider recent messages received and the current state. Now go through available triggers listed above, and think deeply about whether any should be triggered. 
    - If any playbook should be triggered, set $_busy = True and output an appropriate trig? line.
    - If a playbook was executed, look at the message that was received and the result of the playbook execution. If the message sender is expecting a response, enqueue a Say(message sender, result of the playbook execution) call
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
