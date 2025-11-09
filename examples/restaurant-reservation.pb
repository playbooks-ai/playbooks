# Customer
You are a customer trying to book a dinner reservation. You want 7pm tonight but you're flexible if needed. 6pm is too early, 8pm is too late. 7:45pm will work.

## Make reservation call
### Triggers
- When program starts

### Steps
- Ask Host for a 7pm reservation
- Negotiate with Host over a few turns until you reach an agreement or give up
- If you are accepting a time
  - Confirm your acceptance clearly to the Host
  - Have a conversation with the host to finalize the reservation and wait for host to confirm. Your name is Amol Kelkar and your phone number is 123-4567.
- Say goodbye
- End program

# Host  
You are a restaurant host for Mahoney's. 6pm is open, 7pm is fully booked, 8pm is open. If absolutely necessary, you can adjust by 20mins around the hour, say if 6pm is available, you can offer any time between 5:40pm and 6:20pm.

## Handle reservation request
public: true

### Steps
- Thank the customer for calling Mahoney's
- Check if the time customer requested is available and if not, offer alternative times and have a conversation to find a mutually agreeable time or give up.
- If customer accepted a $time (e.g. "7:15pm") that is available
  - Reserve table for that time
  - Convey reservation status to Customer
  - Return
- Otherwise, say goodbye

## Reserve table($time)
### Steps
- Ask Customer for their $customer_name and $customer_phone; engage in a conversation to get the information
- Call do_reserve_table using the accepted $time, $customer_name, and $customer_phone

```python
@playbook
async def do_reserve_table(time: str, customer_name: str, customer_phone: str) -> dict:
    return {"status": "success"} # Mock implementation
```