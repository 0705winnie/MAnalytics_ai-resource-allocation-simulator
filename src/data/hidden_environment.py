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

N_CLUSTERS = 3

CLUSTER_CAPACITY = {
    1: 100,
    2: 100,
    3: 100,
}

SIMULATION_MONTHS = 12
DAYS_PER_MONTH = 30
HOURS_PER_DAY = 24


# Revenue assumptions

# Revenue is earned as:
# revenue = required_units * price_per_unit
# if the request is admitted and completed.
PRICE_PER_UNIT = {
    "VIP": 12,
    "standard": 7,
    "economy": 4,
}


# Demand assumptions

# Expected number of requests per month before applying seasonality.
# Standard requests are most common, VIP requests are less frequent,
# and economy requests are moderately common.
BASE_MONTHLY_ARRIVALS = {
    "VIP": 120,
    "standard": 450,
    "economy": 300,
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


# Required server-unit assumptions

# Each request requires a number of server units.
# These distributions are type-specific.
REQUIRED_UNITS_DISTRIBUTION = {
    "VIP": {
        "values": [8, 10, 12, 15],
        "probabilities": [0.20, 0.35, 0.30, 0.15],
    },
    "standard": {
        "values": [4, 6, 8, 10],
        "probabilities": [0.25, 0.35, 0.25, 0.15],
    },
    "economy": {
        "values": [2, 3, 4, 6],
        "probabilities": [0.30, 0.35, 0.25, 0.10],
    },
}


# Service-time assumptions

# Mean service duration in hours.
# Economy requests are designed to last longer on average,
# creating an opportunity-cost tradeoff.
MEAN_SERVICE_DURATION = {
    "VIP": 4,
    "standard": 6,
    "economy": 9,
}

# Gamma distribution shape parameter used for service durations.
# A Gamma distribution keeps durations positive and right-skewed.
SERVICE_DURATION_GAMMA_SHAPE = 2


# Historical completion assumptions

# These probabilities are used only for the initial synthetic historical dataset.
# The actual event-based simulator may later determine completions through
# capacity dynamics and departure events.
HISTORICAL_COMPLETION_PROBABILITY = {
    "VIP": 0.95,
    "standard": 0.90,
    "economy": 0.85,
}


# Random seed

DEFAULT_RANDOM_SEED = 42