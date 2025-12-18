# ComplexFlow

## Main
### Triggers
- At the beginning

### Steps
- Initialize counter to 0 as a local variable
- set $state_count to 0
- ask user for a number and store in $increment
- counter is counter + $increment
- set $state_count to $state_count + $increment
- say counter is {counter} and state_count is {$state_count}
- ask user for another number and store in $increment2
- counter is counter + $increment2
- set $state_count to $state_count + $increment2
- final is Process(counter, $state_count)
- say the final result is {final}
- End program

## Process(a, b)
### Steps
- local_sum is a + b
- local_product is a * b
- return local_sum + local_product
