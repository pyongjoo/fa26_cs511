#!/bin/bash

# Simple script to set up a Ray cluster with N raylets.
# Usage: ./start_ray.sh [NUM_WORKERS]

export RAY_ENABLE_WINDOWS_OR_OSX_CLUSTER=1
NUM_WORKERS=${1:-4}

# Shutdown on exit
trap "ray stop" EXIT

echo "Setting up Ray cluster with $NUM_WORKERS raylets (1 CPU per raylet)..."

# Start head node
ray start --head --num-cpus=1 --port=6379 --disable-usage-stats

# Start worker nodes
for ((i=1; i<NUM_WORKERS; i++)); do
    ray start --address=127.0.0.1:6379 --num-cpus=1
done

sleep 1

echo "Ray cluster ready with $NUM_WORKERS raylets. Press Ctrl+C to shutdown."

# Keep running
while true; do
    sleep 1
done
