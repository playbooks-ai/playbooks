"""
Performance benchmarks for EventBus async vs sync.

Measures:
- Publish latency
- Subscriber throughput
- Memory usage
- Concurrent performance
"""

import asyncio
import gc
import statistics
import time
import tracemalloc
from typing import List

from playbooks.infrastructure.event_bus import EventBus
from playbooks.core.events import Event


class BenchmarkEvent(Event):
    """Event for benchmarking."""

    def __init__(self, value: int):
        super().__init__()
        self.value = value


class BenchmarkResults:
    """Container for benchmark results."""

    def __init__(self, name: str):
        self.name = name
        self.latencies: List[float] = []
        self.throughput: float = 0
        self.memory_used: float = 0
        self.errors: int = 0

    def add_latency(self, latency: float):
        self.latencies.append(latency)

    def calculate_stats(self):
        if self.latencies:
            return {
                "name": self.name,
                "min_latency_ms": min(self.latencies) * 1000,
                "max_latency_ms": max(self.latencies) * 1000,
                "avg_latency_ms": statistics.mean(self.latencies) * 1000,
                "p50_latency_ms": statistics.median(self.latencies) * 1000,
                "p99_latency_ms": (
                    statistics.quantiles(self.latencies, n=100)[98] * 1000
                    if len(self.latencies) > 100
                    else max(self.latencies) * 1000
                ),
                "throughput_events_per_sec": self.throughput,
                "memory_mb": self.memory_used / 1024 / 1024,
                "errors": self.errors,
            }
        return None


async def benchmark_async_event_bus(
    num_events: int = 10000, num_subscribers: int = 10
) -> BenchmarkResults:
    """Benchmark EventBus async performance."""
    results = BenchmarkResults("EventBus (async)")

    # Setup
    bus = EventBus("bench-session")
    received_count = 0

    async def handler(event):
        nonlocal received_count
        received_count += 1
        # Simulate some work
        await asyncio.sleep(0)

    # Add subscribers
    for i in range(num_subscribers):
        bus.subscribe(BenchmarkEvent, handler)

    # Measure memory before
    gc.collect()
    tracemalloc.start()

    # Benchmark publish latency
    start_time = time.perf_counter()

    for i in range(num_events):
        event_start = time.perf_counter()
        await bus.publish(BenchmarkEvent(i))
        event_end = time.perf_counter()
        results.add_latency(event_end - event_start)

    end_time = time.perf_counter()
    total_time = end_time - start_time

    # Calculate throughput
    results.throughput = num_events / total_time

    # Measure memory
    current, peak = tracemalloc.get_traced_memory()
    results.memory_used = peak
    tracemalloc.stop()

    # Cleanup
    await bus.close()

    # Verify all events received
    expected_count = num_events * num_subscribers
    if received_count != expected_count:
        results.errors = expected_count - received_count

    return results


def benchmark_sync_event_bus(
    num_events: int = 10000, num_subscribers: int = 10
) -> BenchmarkResults:
    """Benchmark synchronous EventBus performance."""
    results = BenchmarkResults("EventBus (threading)")

    # Setup
    bus = EventBus("bench-session")
    received_count = 0

    def handler(event):
        nonlocal received_count
        received_count += 1
        # Simulate some work
        time.sleep(0)

    # Add subscribers
    for i in range(num_subscribers):
        bus.subscribe(BenchmarkEvent, handler)

    # Measure memory before
    gc.collect()
    tracemalloc.start()

    # Benchmark publish latency
    start_time = time.perf_counter()

    for i in range(num_events):
        event_start = time.perf_counter()
        bus.publish(BenchmarkEvent(i))
        event_end = time.perf_counter()
        results.add_latency(event_end - event_start)

    end_time = time.perf_counter()
    total_time = end_time - start_time

    # Calculate throughput
    results.throughput = num_events / total_time

    # Measure memory
    current, peak = tracemalloc.get_traced_memory()
    results.memory_used = peak
    tracemalloc.stop()

    # Verify all events received
    expected_count = num_events * num_subscribers
    if received_count != expected_count:
        results.errors = expected_count - received_count

    return results


async def benchmark_concurrent_publish(
    num_publishers: int = 100, events_per_publisher: int = 100
) -> BenchmarkResults:
    """Benchmark concurrent publishing performance."""
    results = BenchmarkResults("EventBus (concurrent async)")

    # Setup
    bus = EventBus("bench-session")
    received_count = 0

    async def handler(event):
        nonlocal received_count
        received_count += 1

    # Single subscriber
    bus.subscribe(BenchmarkEvent, handler)

    # Publisher coroutine
    async def publisher(publisher_id: int):
        latencies = []
        for i in range(events_per_publisher):
            start = time.perf_counter()
            await bus.publish(BenchmarkEvent(publisher_id * 1000 + i))
            end = time.perf_counter()
            latencies.append(end - start)
        return latencies

    # Measure memory before
    gc.collect()
    tracemalloc.start()

    # Run publishers concurrently
    start_time = time.perf_counter()

    publisher_tasks = [publisher(i) for i in range(num_publishers)]
    all_latencies = await asyncio.gather(*publisher_tasks)

    end_time = time.perf_counter()
    total_time = end_time - start_time

    # Flatten latencies
    for latencies in all_latencies:
        results.latencies.extend(latencies)

    # Calculate throughput
    total_events = num_publishers * events_per_publisher
    results.throughput = total_events / total_time

    # Measure memory
    current, peak = tracemalloc.get_traced_memory()
    results.memory_used = peak
    tracemalloc.stop()

    # Cleanup
    await bus.close()

    # Verify
    if received_count != total_events:
        results.errors = total_events - received_count

    return results


async def benchmark_adapter_performance(num_events: int = 1000) -> BenchmarkResults:
    """Adapter benchmark removed; use EventBus directly."""
    results = BenchmarkResults("EventBus (adapter removed)")
    # No-op benchmark to preserve test harness structure
    results.throughput = num_events / max(0.0001, num_events)  # dummy value
    return results


def print_results(results: List[BenchmarkResults]):
    """Print benchmark results in a formatted table."""
    print("\n" + "=" * 80)
    print("ASYNC EVENT BUS PERFORMANCE BENCHMARK RESULTS")
    print("=" * 80 + "\n")

    # Print header
    print(
        f"{'Benchmark':<25} {'Avg Latency':<12} {'P99 Latency':<12} {'Throughput':<15} {'Memory (MB)':<12} {'Errors':<8}"
    )
    print("-" * 80)

    # Print results
    for result in results:
        stats = result.calculate_stats()
        if stats:
            print(
                f"{stats['name']:<25} "
                f"{stats['avg_latency_ms']:<12.3f} "
                f"{stats['p99_latency_ms']:<12.3f} "
                f"{stats['throughput_events_per_sec']:<15.0f} "
                f"{stats['memory_mb']:<12.2f} "
                f"{stats['errors']:<8}"
            )

    print("\n" + "=" * 80)
    print("DETAILED STATISTICS")
    print("=" * 80 + "\n")

    for result in results:
        stats = result.calculate_stats()
        if stats:
            print(f"\n{stats['name']}:")
            print(f"  Min Latency: {stats['min_latency_ms']:.3f} ms")
            print(f"  Max Latency: {stats['max_latency_ms']:.3f} ms")
            print(f"  Avg Latency: {stats['avg_latency_ms']:.3f} ms")
            print(f"  P50 Latency: {stats['p50_latency_ms']:.3f} ms")
            print(f"  P99 Latency: {stats['p99_latency_ms']:.3f} ms")
            print(f"  Throughput: {stats['throughput_events_per_sec']:,.0f} events/sec")
            print(f"  Memory Used: {stats['memory_mb']:.2f} MB")
            print(f"  Errors: {stats['errors']}")


async def main():
    """Run all benchmarks."""
    print("Starting EventBus performance benchmarks...")
    print("This may take a few moments...\n")

    results = []

    # Benchmark 1: EventBus async
    print("Running EventBus (async) benchmark...")
    results.append(
        await benchmark_async_event_bus(num_events=10000, num_subscribers=10)
    )

    # Benchmark 2: Sync EventBus for comparison
    print("Running EventBus (threading) benchmark...")
    results.append(benchmark_sync_event_bus(num_events=10000, num_subscribers=10))

    # Benchmark 3: Concurrent publishers
    print("Running concurrent publisher benchmark...")
    results.append(
        await benchmark_concurrent_publish(num_publishers=100, events_per_publisher=100)
    )

    # Benchmark 4: Adapter performance (removed)
    print("Running adapter benchmark (removed)...")
    results.append(await benchmark_adapter_performance(num_events=1000))

    # Print results
    print_results(results)

    # Summary
    async_result = results[0].calculate_stats()
    sync_result = results[1].calculate_stats()

    if async_result and sync_result:
        latency_improvement = (
            (sync_result["avg_latency_ms"] - async_result["avg_latency_ms"])
            / sync_result["avg_latency_ms"]
            * 100
        )
        throughput_improvement = (
            (
                async_result["throughput_events_per_sec"]
                - sync_result["throughput_events_per_sec"]
            )
            / sync_result["throughput_events_per_sec"]
            * 100
        )
        memory_reduction = (
            (sync_result["memory_mb"] - async_result["memory_mb"])
            / sync_result["memory_mb"]
            * 100
        )

        print("\n" + "=" * 80)
        print("PERFORMANCE IMPROVEMENTS (EventBus async vs sync)")
        print("=" * 80)
        print(f"  Latency Reduction: {latency_improvement:.1f}%")
        print(f"  Throughput Increase: {throughput_improvement:.1f}%")
        print(f"  Memory Reduction: {memory_reduction:.1f}%")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
