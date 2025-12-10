# Variables
This is a test for the variables management in playbooks

## Main

### Triggers
- At the beginning

### Steps
- set $name to "John"
- set local variable age to 30
- x = age + 5
- y = x * 2
- set local variable gender to "male"
- country = A(userage=age, z=y)
- say the name of the country and the value of y
- End program


## A(userage, z)
### Steps
- set local variable lastname to "Pinkerton"
- say user's name if that information is available to you, otherwise say I don't know
- say user's last name if that information is available to you, otherwise say I don't know
- say user's age if that information is available to you, otherwise say I don't know
- say user's z if that information is available to you, otherwise say I don't know
- say user's gender if that information is available to you, otherwise say I don't know
- ask user their favorite color and $game is and engage user in a conversation till they provide the information
- say last name, favorite color, and $game
- return "India"