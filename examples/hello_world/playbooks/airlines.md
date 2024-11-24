# ListAllPlaybooks
1. Return an array of all playbooks and their triggers, e.g. {"Playbook1": "Trigger1", "Playbook2": null} if Playbook2 has no trigger specified

====

# SelectNextPlaybook

## Trigger
At the start of a conversation to decide which playbook to start with

## Steps
1. $all_playbooks = ListAllPlaybooks()
2. return LLM("Select up to 1 playbook that can be triggered at this time")

====

# FilterAirlines($filters)
always return ["Delta", "Alaska"]

====

# SelectAirlines($condition)

## Trigger
When user specifies a condition that means only a few airlines can be used

## Steps
1. Various filters are available to filter airlines. These are freeBaggage, noCancellationFee.
2. $filters = convert $condition into appropriate filters as a set, e.g. {freeBaggage: false}
3. return FilterAirlines($filters)

====

# FindFlights(optional $airlines, $source, $destination)

## Trigger
When user wants to find or reserve flights

## Steps
1. Tell the user that you will find the flights from $source to $destination, also list the $airlines if they are specified

## Notes
1. Make sure to apply any airline filters before reserving flights

====

# Start

## Trigger
When the user starts a conversation or asks for a greeting.

## Steps
1. Ask user what they want help with
2. $next_playbook = SelectNextPlaybook()
3. Begin executing $next_playbook





I want to fly to the Bay area but only on airlines that have free checked bags