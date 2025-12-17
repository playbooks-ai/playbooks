# Host

## Main

### Triggers
- When program starts

### Steps
- Create a Participant
- Have a meeting with the participant
- End program

## Meeting
meeting: true

### Steps
- Save a random food item name in meeting shared state
- Ask participant to guess the food item name
- Wait for the participant to reveal the food item name
- Check if the food item name is correct
- If correct
    - say "Correct!"
- Otherwise
    - say "Incorrect!" and say the correct food item name and the guess

# Participant

## Meeting
meeting: true

### Triggers
- When invited to a meeting

### Steps
- Wait for the host to ask you to guess the food item name
- Read the food item name from meeting shared state
- Say the food item name
- Wait for the host to check if the food item name is correct
- Say goodbye
