# PatientAgent
An agent that demonstrates adaptive waiting.

## WaitForColleague
### Triggers
- At the beginning

### Steps
- Tell user "Asking my colleague to answer a simple question: What's the answer to life, universe and everything?"
- Create SlowColleague agent $colleague
- Ask $colleague to answer "What's the answer to life, universe and everything?"
- Wait for $answer
- Tell user the answer
- End program

### Notes
- SlowColleague typically responds in 2 seconds, but can take up to 30 seconds when busy. Keep the user informed and entertained frequently while waiting.

# SlowColleague  
A deliberately slow agent for testing.

## Answer($question)
public: true

### Steps
- Wait 30 seconds
- Return a funny answer to the question