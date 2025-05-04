# Artifacts test

```python
@playbook
async def Playbook3():
    await SaveArtifact("another_artifact", "Another artifact", "Secret message 54345.")
    return "Artifact[another_artifact]"

@playbook
async def Playbook4():
    artifact = await LoadArtifact("artifact1.txt")
    await Say("Artifact[artifact1.txt]")
    await Say(artifact.content)
```

## Playbook1

### Steps
- Create an artifact with the name "my_artifact" and the content "This is a test artifact."
- Return the artifact

## Playbook2

### Steps
- Load the artifact "my_artifact" and "another_artifact"
- Show my_artifact to user
- Say the content of my_artifact
- Show another_artifact to user
- Say the content of another_artifact

## Main

### Trigger
- At the start

### Steps
- Run Playbook1
- SaveArtifact("artifact1.txt", "Artifact1", "This is artifact1.")
- Run Playbook3
- Run Playbook2
- Run Playbook4
