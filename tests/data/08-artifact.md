# Artifacts test

```python
@playbook
async def Playbook3():
    await SaveArtifact("another_artifact.md", "Another artifact", "Secret message 54345.")
    return "Artifact[another_artifact.md]"

@playbook
async def Playbook4():
    artifact = await LoadArtifact("artifact1.txt")
    await Say("Artifact[artifact1.txt]")
    await Say(artifact.content)
```

## Playbook1

### Steps
- Create an artifact with the name "my_artifact.txt" and the content "This is a test artifact" followed by a 2 line poem
- Return the artifact

## Playbook2

### Steps
- Load the artifact "my_artifact.txt" and "another_artifact.md"
- Show my_artifact.txt to user
- Say the content of my_artifact.txt
- Show another_artifact.md to user
- Say the content of another_artifact.md

## Main

### Trigger
- At the start

### Steps
- Run Playbook1
- Save "artifact1.txt" with summary "Artifact1" and content "This is artifact1."
- Update "my_artifact.txt" with a 4 line poem followed by "This is my artifact."
- Run Playbook3
- Run Playbook2
- Run Playbook4
