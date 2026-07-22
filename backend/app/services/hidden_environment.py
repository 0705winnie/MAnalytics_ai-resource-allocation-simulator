"""
Hidden environment parameters for the AI-assisted online resource allocation simulator.

This file defines the synthetic "true world" used to generate historical data
and future simulation instances.

Important:
- These parameters are used internally by the data generator and simulator.
- Students should not see these parameters directly.
- Students should only see the historical dataset generated from these assumptions.
"""

# Basic system setup

REQUEST_TYPES = ["VIP", "standard", "economy"]

N_CLUSTERS = 10

# Heterogeneous cluster capacities make routing decisions meaningful:
# small clusters are efficient for small jobs, while large clusters preserve
# feasibility for high-unit VIP requests.
CLUSTER_CAPACITY = {
    1: 12,
    2: 12,
    3: 14,
    4: 14,
    5: 16,
    6: 16,
    7: 18,
    8: 18,
    9: 20,
    10: 20,
}

SIMULATION_MONTHS = 12
DAYS_PER_MONTH = 30
HOURS_PER_DAY = 24


# Revenue assumptions

# Revenue is earned as:
# revenue = required_units * price_per_unit
# if the request is admitted and completed.
PRICE_PER_UNIT = {
    "VIP": 14,
    "standard": 8,
    "economy": 4,
}


# Demand assumptions

# Expected number of requests per month before applying seasonality.
# Standard requests are most common, VIP requests are less frequent,
# and economy requests are moderately common.
BASE_MONTHLY_ARRIVALS = {
    "VIP": 90,
    "standard": 420,
    "economy": 360,
}

# Monthly seasonality multipliers.
# Higher values indicate peak demand months.
MONTHLY_MULTIPLIER = {
    1: 0.85,
    2: 0.90,
    3: 1.00,
    4: 1.05,
    5: 1.10,
    6: 1.20,
    7: 1.35,
    8: 1.25,
    9: 1.10,
    10: 1.00,
    11: 1.15,
    12: 1.30,
}

# Type-specific seasonality creates periods where the best policy changes.
# Students only see this indirectly through historical data.
TYPE_MONTHLY_MULTIPLIER = {
    "VIP": {
        1: 0.90,
        2: 0.90,
        3: 0.95,
        4: 1.00,
        5: 1.10,
        6: 1.20,
        7: 1.35,
        8: 1.20,
        9: 1.05,
        10: 1.00,
        11: 1.15,
        12: 1.35,
    },
    "standard": {
        1: 0.95,
        2: 0.95,
        3: 1.00,
        4: 1.05,
        5: 1.05,
        6: 1.10,
        7: 1.15,
        8: 1.10,
        9: 1.05,
        10: 1.00,
        11: 1.05,
        12: 1.10,
    },
    "economy": {
        1: 1.10,
        2: 1.10,
        3: 1.05,
        4: 1.00,
        5: 1.00,
        6: 0.95,
        7: 0.90,
        8: 0.95,
        9: 1.00,
        10: 1.05,
        11: 1.00,
        12: 0.95,
    },
}


# Required server-unit assumptions

# Each request requires a number of server units.
# These distributions are type-specific.
REQUIRED_UNITS_DISTRIBUTION = {
    "VIP": {
        "values": [10, 12, 15, 18],
        "probabilities": [0.15, 0.35, 0.30, 0.20],
    },
    "standard": {
        "values": [5, 7, 9, 12],
        "probabilities": [0.25, 0.35, 0.25, 0.15],
    },
    "economy": {
        "values": [3, 5, 7, 9],
        "probabilities": [0.30, 0.35, 0.25, 0.10],
    },
}


# Service-time assumptions

# Mean service duration in hours.
# Economy requests are designed to last longer on average,
# creating an opportunity-cost tradeoff.
MEAN_SERVICE_DURATION = {
    "VIP": 5,
    "standard": 9,
    "economy": 20,
}

# Gamma distribution shape parameter used for service durations.
# A Gamma distribution keeps durations positive and right-skewed.
SERVICE_DURATION_GAMMA_SHAPE = 2


# Historical completion assumptions

# These probabilities are used only for the initial synthetic historical dataset.
# The actual event-based simulator may later determine completions through
# capacity dynamics and departure events.
HISTORICAL_COMPLETION_PROBABILITY = {
    "VIP": 0.96,
    "standard": 0.88,
    "economy": 0.76,
}


# Random seed

DEFAULT_RANDOM_SEED = 42
