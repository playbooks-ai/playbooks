from playbooks.utils.markdown_to_ast import markdown_to_ast


class BuiltinPlaybooks:
    """Provides built-in playbooks that are automatically added to every agent."""

    @staticmethod
    def get_ast_nodes():
        """Get AST nodes for built-in playbooks.

        Returns:
            List of AST nodes representing built-in playbooks.
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
```        
'''

        return markdown_to_ast(code_block)["children"]
