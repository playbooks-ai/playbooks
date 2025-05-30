# This program tests markdown playbook calls

## Main
### Triggers
- At the beginning

### Steps
- $r = 50
- $s = $r + 10
- Call A(10)
- Say goodbye

## A($x)
### Steps
- Say $x
- Call B($x)

## B($y)
### Steps
- Say $y
- $p = C($y) * 3
- Say $p

## C($z)
### Steps
- Say $z
- return 100