# Factor Family Weight Constraints

The lifecycle set contains `price_volume` and `risk` families. At each monthly rebalance, raw non-negative weights are normalized and each family is capped at 65%. Excess weight is redistributed to uncapped families. A 65% cap is used because a 35% cap would be infeasible with only two represented families. Size is an exposure control rather than an alpha family; fundamental families are excluded due five-ticker coverage. All caps use contemporaneously available family labels and past-only signals.
