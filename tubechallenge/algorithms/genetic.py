from datetime import datetime
from importlib.metadata import version
import json
import logging
import numpy as np
import os
import random
import secrets

from tubechallenge.algorithms.constants import PARK_STATION_IDS
from tubechallenge.db import line, station
from tubechallenge.db.db import SessionLocal
from tubechallenge.db.tables import Station
from tubechallenge.utils.stats import get_stats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_initial_routes(
    station_list: list[Station], origin_id: int, pop_size: int
) -> list[list[int]]:
    """Create routes for 0th generation, i.e. initial generation.

    Args:
        station_list (list[Station]): list of station records.
        origin_id (str): station database ID for starting station.
        pop_size (int): number of routes to create.

    Returns:
        list of routes.
    """
    # Remove first station from station list
    stations_to_shuffle = [
        stn.id for stn in station_list if stn.id != origin_id
    ]

    routes = []

    # Shuffle routes
    for _ in range(pop_size):
        route = stations_to_shuffle[:]
        random.shuffle(route)
        route.insert(0, origin_id)  # Prepend first station
        routes.append(route)

    return routes


def evaluate_route(route: list[int], journeys: dict):
    """Find a valid route between stations. A tube train must be used to either
    arrive at or depart a station in order for the route to be considered
    valid. Naturally, arriving and departing a station using a tube train is
    also allowed. Currently, a greedy algorithm is employed to select a valid
    route.

    Args:
        route (list[int]): route consisting of list of database IDs for
          stations in the order in which they should be visited.
        journeys (dict): pre-computed journeys between stations.

    Returns:
        dictionary of total duration and route information.
    """
    tube_visited = set()  # stations visited by tube
    full_journey = []
    total_duration = 0

    for origin, destination in zip(route[:-1], route[1:]):
        candidates = journeys[(origin, destination)]["candidates"]

        # Find valid candidate journeys
        valid_candidates = []
        for candidate in candidates:
            visit_origin = candidate["tube_start"] and origin not in tube_visited
            visit_destination = candidate["tube_end"] and destination not in tube_visited
            if visit_origin or visit_destination:
                valid_candidates.append(candidate)

        # There will always be at least one valid route
        best_candidate = min(valid_candidates, key=lambda c: c["duration"])

        total_duration += best_candidate["duration"]

        full_journey.extend(best_candidate["path"])

        if best_candidate["tube_start"]:
            tube_visited.add(origin)
        if best_candidate["tube_end"]:
            tube_visited.add(destination)

    return {"duration": total_duration, "journey": full_journey}


def get_route_fitnesses(population: list[list[int]], journeys: dict) -> list:
    """Calculate fitnesses for routes and sort by fitness. The fitness metric
    is the duration; the lower the duration, the fitter the route.

    Args:
        population (list[list[int]]): list of routes to assess.
        journeys (dict): pre-computed journeys between stations.

    Returns:
        sorted routes with durations.
    """
    results = []
    for route in population:
        evaluation = evaluate_route(route, journeys)
        results.append((route, evaluation["duration"], evaluation["journey"]))

    results.sort(key=lambda route: route[1])

    return results


def order_crossover(mother: list[int], father: list[int]) -> list[int]:
    """Implement Order Crossover to create child from parents.

    Args:
        mother (list[int]): route of first parent.
        father (list[int]): route of second parent.

    Returns:
        new route.
    """
    # Choose two cut points
    size = len(mother)
    a, b = sorted(random.sample(range(size), 2))

    # Copy slice between two points from mother to child
    child = [None] * size
    child[a:b] = mother[a:b]

    # Fill remaining stations from father
    # Both mother and father have same starting station, so no need to fix this
    # as order is preserved
    missing_stations = [stn for stn in father if stn not in child]
    child[:a] = missing_stations[:a]
    child[b:] = missing_stations[a:]

    return child


def procreate(routes: list, n_children: int):
    """Splice routes together to create children that will form part of next
    generation.

    Args:
        routes (list): routes from previous generation ordered by duration.
        n_children (int): number of children (i.e. new routes) to generate.

    Returns:
        list of new routes.
    """
    # Select parents randomly with weights proportional to the reciprocal of
    # the duration.
    weights = [1 / duration for _, duration, _ in routes]
    children = []
    for _ in range(n_children):
        mother, father = random.choices(routes, weights=weights, k=2)
        children.append(order_crossover(mother[0], father[0]))

    return children


def mutate(route: list[int]) -> list[int]:
    """Perform inversion mutation. Mutate route by reversing a sub-sequence of
    stations selected randomly.

    Args:
        route (list[int]): route to be mutated.

    Returns:
        mutated route.
    """
    # First station is fixed so sample from index 1
    a, b = sorted(random.sample(range(1, len(route)), 2))
    route[a:b] = reversed(route[a:b])

    return route


def get_new_population(
    routes: list, elite_size: int, mutation_rate: float
) -> list[list[int]]:
    """Create next generation of routes.

    Args:
        routes (list): routes from previous generation ordered by duration.
        elite_size (int): number of the best routes to pass down to the next
          generation.
        mutation_rate (float): proportion of routes that will undergo mutation,
          i.e. two stations will swap places in an effort to step out of any
          local minima.

    Returns:
        the next generation of routes.
    """
    n_children = len(routes) - elite_size

    children = procreate(routes, n_children)
    next_generation = [route for route, _, _ in routes[:10]]
    next_generation += children

    for i, child in enumerate(next_generation):
        if random.random() < mutation_rate:
            next_generation[i] = mutate(child)

    return next_generation


def get_line_map() -> dict[int, str]:
    """Query database to get map of line IDs to line names.

    Returns:
        dictionary of line IDs to line names.
    """
    with SessionLocal() as session:
        lines = line.get_many(session=session)

    line_map = {}
    for ln in lines:
        line_map[ln.id] = ln.name

    return line_map


def extract_route(
    route: list[list[str, int | None, float]], line_map: dict[int, str]
) -> dict:
    """Format route for output.

    Args:
        route (list[list[str, int | None, float]]): detailed route information.
        line_map (dict[int, str]): map of line IDs to line names.

    Returns:
        dictionary of route in more readable format.
    """
    journey_details = []
    for station, line_id, journey_time in route:
        journey_details.append(
            {
                "name": station,
                "line": line_map.get(line_id, "None"),
                "time": journey_time,
            }
        )

    return journey_details


def genetic_algorithm(
    journeys: list,
    first_station: str,
    station_list: list[str] | None = None,
    n_generations: int = 300,
    pop_size: int = 200,
    elite_size: int = 10,
    mutation_rate: float = 0.1,
    random_seed: int | None = None
):
    """Implement genetic algorithm to find best route between stations.

    Args:
        journeys (list): pre-computed journeys between stations.
        first_station (str): station ID for starting station.
        station_list (list[str]): list of station IDs to find optimal route
          between.
        n_generations (int): number of generations to simulate.
        pop_size (int): number of routes per generation.
        elite_size (int): number of the best routes to pass down to next
          generation.
        mutation_rate (float): proportion of routes that will undergo mutation,
          i.e. two stations will swap places, in an effort to step out of any
          local minima.
        random_seed (int): seed for random number generation.
    """
    # Use Park stations list if one is not provided
    if not station_list:
        station_list = PARK_STATION_IDS

    # Set random seed
    if not random_seed:
        random_seed = int(secrets.randbits(32))
    random.seed(random_seed)

    # Build metadata
    metadata = {
        "version": version("tubechallenge"),
        "firstStation": first_station,
        "stationList": station_list,
        "populationSize": pop_size,
        "generations": n_generations,
        "eliteSize": elite_size,
        "mutationRate": mutation_rate,
        "random_seed": random_seed,
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
    }

    # Ensure origin station is included on station list
    if first_station not in station_list:
        station_list.append(first_station)
        logger.info(f"Origin station {first_station} included in station list")

    with SessionLocal() as session:
        station_list = station.get_many(
            session=session, station_ids=station_list
        )
        origin_id = station.get_one(
            station_id=first_station, session=session
        ).id

    # Create initial population of routes
    population = create_initial_routes(station_list, origin_id, pop_size)

    journeys = {tuple(k): v for k, v in journeys}

    shortest_duration_gen = []  # duration of best route per generation
    mean_gen = []  # mean duration per generation
    sigma_gen = []  # standard deviation from mean per generation
    iqr_gen = []  # interquartile range of durations per generation
    for gen in range(n_generations):
        routes = get_route_fitnesses(population, journeys)

        shortest_duration_gen.append(float(routes[0][1]))


        durations = [route[1] for route in routes]
        mean_gen.append(float(np.mean(durations)))
        sigma_gen.append(float(np.std(durations)))
        q25, q75 = np.percentile(durations, [25, 75])
        iqr_gen.append(float(q75 - q25))

        # TODO: This is unncessary for final generation
        population = get_new_population(routes, elite_size, mutation_rate)

    durations_final_gen = durations

    # Build statistics
    generations = list(range(n_generations))
    statistics = {
        "generations": generations,
        "mean": mean_gen,
        "sigma": sigma_gen,
        "iqr": iqr_gen,
        "shortestDurations": shortest_duration_gen,
        "finalGenerationDurations": durations_final_gen,
    }

    # Fit exponential decay to shortest durations per generation and derive
    # metrics
    exp_fit_params, fit_generations, fit_durations, metrics = get_stats(
        generations, shortest_duration_gen
    )
    fitting = {
        "exponentialDecay": {
            "parameters": {
                "T0": exp_fit_params[0],
                "tau": exp_fit_params[1],
                "plateau": exp_fit_params[2],
            },
            "generations": fit_generations,
            "durations": fit_durations,
            "r_squared": metrics[0],
            "rmse": metrics[1],
            "mae": metrics[2],
        },
    }

    # Get top unique routes in final generation
    line_map = get_line_map()
    seen_routes = set()
    best_unique_routes = []
    rank = 0
    for route in routes:
        stations = tuple(route[0])
        if stations not in seen_routes:
            rank += 1
            best_unique_routes.append(
                {
                    "rank": rank,
                    "total_duration": route[1],
                    "stations": extract_route(route[2], line_map),
                }
            )
            seen_routes.add(stations)

        # Only take top 5 shortest routes at most
        if rank == 5:
            break

    return {
        "metadata": metadata,
        "statistics": statistics,
        "fitting": fitting,
        "routes": best_unique_routes,
    }
