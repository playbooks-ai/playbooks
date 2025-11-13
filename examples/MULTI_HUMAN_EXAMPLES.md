# Multi-Human Playbook Examples

This directory contains examples demonstrating the new multi-human declarative syntax in Playbooks.

---

## Quick Start

### Minimal Example: `hello_world_multi_human_minimal.pb`

The simplest possible multi-human program:

```markdown
# Alice:Human
# Bob:Human
# Greeter:AI

## Main
### Steps
- Say("Alice", "Hello Alice!")
- Say("Bob", "Hello Bob!")
```

**Run it**:
```bash
playbooks run examples/hello_world_multi_human_minimal.pb --stream
```

**What it demonstrates**:
- Declaring multiple humans with `:Human` type annotation
- Each human gets unique ID
- Default streaming delivery for both humans

---

## Full Example: `hello_multi_human.pb`

Shows delivery preferences and meeting features:

```markdown
# Alice:Human
metadata:
  delivery_channel: streaming
  meeting_notifications: all

# Bob:Human
metadata:
  delivery_channel: buffered
  meeting_notifications: targeted
```

**What it demonstrates**:
- Per-human delivery preferences
- Meeting notifications (all vs targeted)
- Streaming vs buffered delivery
- How different humans see different views

---

## Meeting Example: `multi_human_meeting.pb`

Complete team meeting scenario:

```markdown
# Alice:Human (PM, all notifications)
# Bob:Human (Developer, targeted)
# Carol:Human (Designer, no notifications)
# Facilitator:AI

## TeamStandup
meeting: true
required_attendees: [Alice, Bob, Carol]
```

**What it demonstrates**:
- Multi-human meetings
- Three different notification modes
- Per-human streaming control
- Team collaboration patterns

---

## Syntax Reference

### Declare a Human Agent

```markdown
# <Name>:Human
metadata:
  name: <display-name>              # Optional, defaults to <Name>
  delivery_channel: <mode>          # streaming | buffered | custom
  streaming_enabled: <bool>         # true | false
  meeting_notifications: <mode>     # all | targeted | none
  buffer_timeout: <seconds>         # For buffered delivery
```

### Delivery Modes

**Streaming** (default):
```markdown
# Alice:Human
metadata:
  delivery_channel: streaming
  streaming_enabled: true
```
- Messages appear character-by-character in real-time
- Best for interactive UIs (terminal, web chat)

**Buffered**:
```markdown
# Bob:Human
metadata:
  delivery_channel: buffered
  buffer_timeout: 60.0
```
- Messages accumulate and deliver in batches
- Best for non-interactive delivery (email, SMS)
- Auto-disables streaming

**Custom**:
```markdown
# Carol:Human
metadata:
  delivery_channel: custom
  delivery_handler: my_custom_handler
```
- Hook for application-specific delivery
- Requires providing custom handler function

### Meeting Notification Modes

**All** - Receive all meeting messages:
```markdown
metadata:
  meeting_notifications: all
```
- Gets every message in real-time
- Best for active participants, meeting hosts

**Targeted** - Only when mentioned:
```markdown
metadata:
  meeting_notifications: targeted
```
- Only receives messages when mentioned by name
- Example: "Bob, what do you think?"
- Best for passive participants

**None** - No meeting notifications:
```markdown
metadata:
  meeting_notifications: none
```
- Doesn't receive meeting messages
- Can still participate if explicitly engaged
- Best for optional attendees, observers

---

## Common Patterns

### Team Meeting with Different Roles

```markdown
# Manager:Human
metadata:
  meeting_notifications: all  # Needs to hear everything

# Developer:Human  
metadata:
  meeting_notifications: targeted  # Only when called on

# Designer:Human
metadata:
  meeting_notifications: none  # Doesn't attend all meetings

# Facilitator:AI
```

### Customer Support

```markdown
# Customer:Human
metadata:
  delivery_channel: streaming  # Real-time chat

# SupportAgent:Human
metadata:
  delivery_channel: buffered  # Batch notifications
  meeting_notifications: targeted

# AIAssistant:AI
```

### Training Session

```markdown
# Instructor:Human
metadata:
  meeting_notifications: all

# Student1:Human
# Student2:Human
# Student3:Human

# Trainer:AI
```

---

## Migration from Single Human

### Before (Old Syntax)
```markdown
# Host:AI

## Main
### Steps
- Say("human", "Hello!")  # Hardcoded "human"
```

### After (New Syntax) - Backward Compatible
```markdown
# Host:AI

## Main
### Steps
- Say("User", "Hello!")  # Auto-creates User:Human
```

### After (Explicit)
```markdown
# Alice:Human

# Host:AI

## Main  
### Steps
- Say("Alice", "Hello Alice!")  # Explicit, clear
```

---

## Tips & Best Practices

### 1. **Always Use Explicit Names**
```markdown
# Good
# Alice:Human
# Bob:Human

# Avoid (ambiguous with multiple humans)
# User:Human
# Human:Human
```

### 2. **Set Meaningful Display Names**
```markdown
# Good
metadata:
  name: Alice Chen

# Avoid
metadata:
  name: User123
```

### 3. **Choose Appropriate Notification Mode**
- **all**: For meeting hosts, active participants
- **targeted**: For team members, passive participants  
- **none**: For optional attendees, observers

### 4. **Match Channel to Use Case**
- **streaming**: Interactive UIs (terminal, web, mobile)
- **buffered**: Async delivery (email, batch notifications)
- **custom**: Special integrations (SMS, Slack, etc.)

---

## Troubleshooting

### Multiple Humans Get Same ID
**Problem**: Using generic names like "User" for multiple humans

**Solution**: Use unique, descriptive names:
```markdown
# Alice:Human  # Good - unique
# Bob:Human    # Good - unique
# User:Human   # Avoid with multiple humans
```

### Human Not Receiving Messages
**Check**:
1. Is streaming_enabled = true?
2. Is meeting_notifications appropriate?
3. Is observer subscribed to correct channel?
4. Is target_human_id set correctly on observer?

### AI Agent Not Created
**Check**:
1. Does it have a trigger (e.g., `At the beginning`)?
2. Is there a public.json block? (Can be empty: `[]`)

---

## More Information

- **Full Documentation**: See `design/architecture_overhaul/`
- **ADR 006**: Multi-Human Declarative Syntax decision record
- **Phase 4 Summary**: Complete implementation details
- **Tests**: `tests/unit/test_multi_human_integration.py` for examples

---

## Feedback

These examples demonstrate the new multi-human capabilities. The features are:
- ✅ Production-ready
- ✅ Well-tested (51 new tests)
- ✅ Backward compatible
- ✅ Fully documented

Try them out and build your own multi-human scenarios!

