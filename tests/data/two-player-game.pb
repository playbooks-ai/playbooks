# Host

## Main
### Triggers
- When program starts

### Steps
- Welcome the user and explain that you're a game show host who can orchestrate AI agents playing games
- Ask the user what $game they would like to watch (e.g., tic-tac-toe, connect four, checkers)
- Tell user you'll set up a match between two AI players for the selected game
- Create two players with creative gamer names
- Join the game room with the the two players and the user
- Conclude by sharing the outcome

## Game Room
meeting: true

### Steps
- Welcome both players to the game show
- Announce what game will be played: $game
- Explain the rules briefly and which player will go first
- Initialize and compactly display the starting game board, e.g. 1X3|4X6|7O9 for tic-tac-toe
- Set turn_count to 0
- While the game is not finished and turn_count < 100
  - Increment turn_count
  - Show current game state
  - Select the player whose turn it is based on the game rules
    - Openly ask the player to make their move
    - Validate the move is legal
    - If move is valid
      - Update game state
      - Tell the move and updated game state
    - Otherwise
      - Openly ask the player to try again with a valid move
  - Check for win condition or draw
  - If game is over
    - Display final game state
    - If there's a winner
      - Announce the winner
    - Otherwise
      - Announce that it's a draw
    - Thank both players for the match
    - End meeting
    - Return
- If turn limit reached
  - Say that the game exceeded the maximum turns so it's a draw
  - End meeting
  - Return

# Player

## Game Playing Meeting
meeting: true

### Steps
- Introduce yourself, ready to play
- Note which game is being played when announced
- While the game is active
  - When asked to make a move
    - Analyze current game state
    - Think about the best possible move using game strategy
    - Clearly announce your move (e.g., "I place X at position 5" or "I move from A3 to B4")
  - When told your move is invalid
    - Apologize for the error
    - Recalculate a valid move
    - Announce the corrected move
  - When opponent makes a move
    - Update your internal game state
  - When game ends
    - If you won
      - Thank the host and say "Good game!"
    - If you lost
      - Congratulate your opponent on their victory
    - If draw
      - Acknowledge it was a well-matched game
  - Otherwise
    - Observe carefully but don't say anything
