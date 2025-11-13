<!-- # Hello World: Multi-Human Example
#
# A simple example demonstrating multiple human agents with different
# delivery preferences interacting with an AI greeter agent. -->

# Alice:Human
Alice is a team lead who wants real-time updates.
metadata:
  name: Alice
  delivery_channel: streaming
  meeting_notifications: all

# Bob:Human
Bob is a developer who prefers buffered messages.
metadata:
  name: Bob
  delivery_channel: buffered
  meeting_notifications: targeted

# Greeter:AI
A friendly AI agent that greets each team member.

## Main
### Triggers
- At the beginning

### Steps
- Greet Alice with a personalized message and tell her that her messages will stream in real-time.
- Greet Bob with his indicating his messages will be delivered buffered
- Start and run a team introduction meeting with Alice and Bob
- End the program

## TeamIntroduction
meeting: true
required_attendees: [Alice, Bob]

### Steps
- Welcome everyone to the meeting
- Tell everyone that the meeting is concluded
- Return

<!-- # How it works:
#
# When you run this playbook:
#
# 1. Alice (streaming, meeting_notifications: all):
#    - Sees all messages character-by-character as they're generated
#    - In meetings: Receives every message in real-time
#
# 2. Bob (buffered, meeting_notifications: targeted):
#    - Messages accumulate and deliver in batches
#    - In meetings: Only receives messages when mentioned ("Bob, hello!")
#
# 3. Greeter (AI agent):
#    - Executes the Main playbook at startup
#    - Can create meetings and broadcast messages
#
# To test different delivery modes:
# - Change Alice's delivery_channel to "buffered" to see batched delivery
# - Change Bob's meeting_notifications to "all" to receive all meeting messages
# - Add more humans with different preferences!
 -->
