# Order Status Customer Support Agent

## AuthenticateUserFlow() -> $authToken

### Trigger
01:CND When the user is not yet authenticated but requests an order status

### Steps
01:EXT Ask("Please provide your email address.")
02:YLD
03:EXE $email = parse email from user input
04:EXT Ask("Please provide your pin.")
05:YLD
06:EXE $pin = parse pin from user input
07:EXT AuthenticateUser($email, $pin)
08:YLD
09:EXE $authToken = store the returned token
10:CND If $authToken is invalid
  10.01:EXT Ask("Please re-confirm your email address.")
  10.02:YLD
  10.03:EXE $email = parse email from user input
  10.04:EXT Ask("Please re-confirm your pin.")
  10.05:YLD
  10.06:EXE $pin = parse pin from user input
  10.07:EXT AuthenticateUser($email, $pin)
  10.08:YLD
  10.09:EXE $authToken = store the returned token
  10.10:CND If $authToken is invalid
    10.10.01:EXT Ask("Please provide your SSN.")
    10.10.02:YLD
    10.10.03:EXE $ssn = parse SSN from user input
    10.10.04:EXT Ask("Please provide your date of birth.")
    10.10.05:YLD
    10.10.06:EXE $dob = parse date of birth from user input
    10.10.07:EXT AuthenticateUser2($ssn, $dob)
    10.10.08:YLD
    10.10.09:EXE $authToken = store the returned token
    10.10.10:CND If $authToken is invalid
      10.10.10.01:EXT Say("Unable to authenticate. Please contact support for further assistance.")
      10.10.10.02:RET return None
11:RET return $authToken

### Notes
N1 This flow attempts to authenticate via pin first. If that fails twice, it uses SSN and DOB.
N2 If authentication fails even after SSN/DOB, the flow ends.

====

## CheckOrderStatusFlow($authToken) -> None

### Trigger
01:CND When the user is authenticated and requests order status

### Steps
01:CHK N1 Ensure $authToken is valid
02:EXT Ask("Please provide your order ID.")
03:YLD
04:EXE $orderID = parse order ID from user input
05:EXT GetOrderStatus($orderID)
06:YLD
07:EXE $orderStatus = store the returned status
08:EXE $expectedDeliveryDate = $orderStatus.expectedDeliveryDate
09:EXT Say("Your order {$orderID} is expected to be delivered on {$expectedDeliveryDate}.")
10:RET return None

### Notes
N1 Always confirm that $authToken is valid before calling GetOrderStatus.
N2 The $orderStatus dictionary includes the keys: orderID, expectedDeliveryDate.

====

## CheckOrderStatusMain() -> None

### Trigger
01:EVT When the user asks to get order status

### Steps
01:CND If user is not authenticated
  01.01:INT $authToken = AuthenticateUserFlow()
02:CND If $authToken is valid
  02.01:INT CheckOrderStatusFlow($authToken)
03:CND else
  03.01:EXT Say("We couldn't complete your request. Please contact customer support or try again later.")
04:RET return None

### Notes
N1 This is the main entry point for the "get order status" request.
N2 If authentication fails, the flow ends with an apology and a suggestion to contact support.