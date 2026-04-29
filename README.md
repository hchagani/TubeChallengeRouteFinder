# Tube Challenge Route Finder

## Introduction
The Tube Challenge is a competition to visit 272 London Underground stations in the fastest time. A visit is defined as either arriving or departing a station by a London Underground service. The current World record is 17 hours, 46 minutes and 48 seconds, held by Robin Otter and Thomas Sheat (10th August 2024).

The challenge is similar to the Travelling Salesman Problem (TSP), in whcih a salesman needs to visit a set number of locations following the shortest possible route. As the number of possible rotues is given by $n!$ where $n$ is the number of locations to visit, determining the optimal route by brute force becomes impractical for high $n$. One technique is to find a solution close to the optimum by employing a genetic algorithm.

This program retrieves information on stations, lines and journey times from Transport for London's APIs and uses A* pathfinding and genetic algorithms to find the quickest routes between London Underground stations.
