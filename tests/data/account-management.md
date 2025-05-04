# Account Management Assistant
This assistant helps you manage various aspects of your account, such as balance, transactions, email, password, status, and locking.

```python
# Assume 'Say' is a built-in function available to playbooks for user output.
# Assume the playbook execution environment implicitly manages state variables like $authToken.

@playbook
async def AuthenticateUser(userId: str, password: str) -> str:
  """
  Authenticates user via simulated backend check.
  Returns a simulated auth token string on success, or None on failure.
  Uses Say() for user feedback during the process.
  """
  # Simulate backend credential check (No Say() for internal actions)
  if userId == "user123" and password == "pass456":
    Say("Authentication successful.")
    # Return a simulated token
    return f"TOKEN_{userId}_VALID"
  else:
    Say("Authentication failed. Please check your User ID and Password.")
    # Return None to indicate failure
    return None

@playbook
async def get_account_balance(authToken: str) -> str:
  """
  Fetches and returns the account balance string.
  Requires a valid authToken.
  """
  if not authToken:
    # This case should ideally be caught by the EnsureAuthentication playbook
    return "Error: Authentication token was missing."
  # Simulate backend lookup
  balance = 1234.56 # Example value
  # Return the result string
  return f"Your current account balance is ${balance}."

@playbook
async def get_recent_transactions(authToken: str) -> str:
  """
  Fetches and returns recent transactions as a formatted string.
  Requires a valid authToken.
  """
  if not authToken:
    return "Error: Authentication token was missing."
  # Simulate backend lookup
  transactions = ["- $50.00 Groceries", "+ $1000.00 Paycheck", "- $25.50 Coffee"] # Example
  # Return the formatted result string
  return "Here are your recent transactions:\n" + "\n".join(transactions)

@playbook
async def update_email_address(authToken: str, newEmail: str) -> str:
  """
  Updates the user's email address via simulated backend.
  Requires a valid authToken and the new email address.
  Uses Say() to confirm the action being taken.
  """
  if not authToken:
    return "Error: Authentication token was missing."
  # Add validation for email format in a real system
  # Inform user action is starting
  Say(f"Attempting to update your email address to {newEmail}...")
  # Simulate backend update success
  # Return the result string
  return f"Your email address has been successfully updated to {newEmail}."

@playbook
async def send_password_reset_link(userId: str) -> str:
  """
  Initiates the password reset process via simulated email dispatch.
  Requires the User ID associated with the account.
  Uses Say() to confirm the action being taken.
  """
  if not userId:
    return "Error: User ID is required to send a password reset link."
  # Inform user action is starting
  Say(f"Sending password reset link to the email associated with user ID {userId}...")
  # Simulate sending email success
  # Return the result string
  return f"A password reset link has been sent to your registered email address. Please check your inbox."

@playbook
async def get_account_status(authToken: str) -> str:
  """
  Fetches and returns the account status string.
  Requires a valid authToken.
  """
  if not authToken:
    return "Error: Authentication token was missing."
  # Simulate backend lookup
  status = "Active" # Example
  # Return the result string
  return f"Your account status is currently: {status}."

@playbook
async def lock_account(authToken: str) -> str:
  """
  Locks the user's account via simulated backend action.
  Requires a valid authToken.
  Uses Say() to confirm the action being taken.
  """
  if not authToken:
    return "Error: Authentication token was missing."
  # Inform user action is starting
  Say("Attempting to lock your account for security...")
  # Simulate backend action success
  # Return the result string
  return "Your account has been temporarily locked. Please contact customer support if you need to unlock it."
```

## Begin
### Triggers
- At the beginning

### Steps
- Welcome the user and inform the user that you can help with  account management tasks like checking your balance, viewing transactions, updating your email, resetting your password, checking status, or locking your account.
- Ask user their name and ask what they would like help with

## EnsureAuthentication
### Steps
- If $authToken is not present or not valid
  - Ask for User ID and Password
  - $authToken = AuthenticateUser using $userId and $password
  - If $authToken is still not valid, retry asking user up to 2 times and then Handoff() if needed

## HandleCheckBalance
### Triggers
- When the user asks to check their account balance
### Steps
- Ensure user is authenticated
- If $authToken is valid
  - get_account_balance using the $authToken
  - Tell the user the account balance
- Otherwise
  - Handoff()

## HandleViewTransactions
### Triggers
- When the user asks to view recent transactions
### Steps
- Ensure user is authenticated
- If $authToken is valid
  - get_recent_transactions using the $authToken
  - provide user information about transactions
- Otherwise
  - Handoff()

HandleUpdateEmail
Triggers
When the user asks to update their email address

Steps
Run the EnsureAuthentication playbook

If $isAuthenticated is true:

Ask the user for their new email address.

update_email_address using the $authToken and $newEmail

Tell the user the $result

HandlePasswordReset
Triggers
When the user asks to reset their password

Steps
Ask the user for their User ID or registered email address.

Let $userId be the provided identifier.

send_password_reset_link using the $userId

Tell the user the $result

HandleCheckStatus
Triggers
When the user asks about their account status

Steps
Run the EnsureAuthentication playbook

If $isAuthenticated is true:

get_account_status using the $authToken

Tell the user the $result

HandleLockAccount
Triggers
When the user asks to lock their account

Steps
Run the EnsureAuthentication playbook

If $isAuthenticated is true:

lock_account using the $authToken

Tell the user the $result

Fallback
Triggers
When the user input does not match any other trigger

Steps
Say "Sorry, I can help with balance checks, transactions, email updates, password resets, status checks, or locking your account. Could you please rephrase your request?"