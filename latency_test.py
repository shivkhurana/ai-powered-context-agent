"""
Latency testing and profiling tool
Runs performance tests to verify sub-800ms response time SLA
"""

import asyncio
import httpx
import time
import statistics
import json
from typing import List, Dict
from datetime import datetime
from pathlib import Path

# Test configuration
API_BASE_URL = "http://localhost:8000/api/v1"
SLA_MS = 800  # Target latency
NUM_QUERIES = 50
QUERIES = [
    "What is machine learning?",
    "Explain deep learning",
    "How does neural networks work?",
    "What are transformers?",
    "Explain LSTM networks",
    "What is gradient descent?",
    "Explain backpropagation",
    "What is overfitting?",
    "How to regularize models?",
    "What is batch normalization?"
] * 5  # Repeat to get 50 queries


class LatencyTester:
    """Latency testing and profiling"""
    
    def __init__(self, base_url: str = API_BASE_URL, sla_ms: float = SLA_MS):
        self.base_url = base_url
        self.sla_ms = sla_ms
        self.results: List[Dict] = []
    
    async def test_single_query(self, client: httpx.AsyncClient, query: str) -> Dict:
        """Test latency for single query"""
        start_time = time.time()
        
        try:
            response = await client.post(
                f"{self.base_url}/query",
                json={
                    "query": query,
                    "use_rag": True,
                    "include_metadata": True
                },
                timeout=10.0
            )
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "query": query,
                    "status": "success",
                    "response_time_ms": elapsed_ms,
                    "execution_time_ms": data.get("metadata", {}).get("execution_time_ms", 0),
                    "llm_time_ms": data.get("metadata", {}).get("llm_execution_time_ms", 0),
                    "confidence": data.get("confidence_score", 0),
                    "under_sla": elapsed_ms <= self.sla_ms
                }
            else:
                return {
                    "query": query,
                    "status": f"error_{response.status_code}",
                    "response_time_ms": elapsed_ms,
                    "under_sla": False
                }
        
        except asyncio.TimeoutError:
            elapsed_ms = (time.time() - start_time) * 1000
            return {
                "query": query,
                "status": "timeout",
                "response_time_ms": elapsed_ms,
                "under_sla": False
            }
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return {
                "query": query,
                "status": f"error: {str(e)}",
                "response_time_ms": elapsed_ms,
                "under_sla": False
            }
    
    async def run_latency_tests(self, queries: List[str] = None):
        """Run latency tests for multiple queries"""
        queries = queries or QUERIES
        
        print("=" * 80)
        print("AI Data Retrieval Agent - Latency Testing")
        print("=" * 80)
        print(f"Target SLA: {self.sla_ms}ms")
        print(f"Number of queries: {len(queries)}")
        print(f"API Base URL: {self.base_url}")
        print("=" * 80)
        print()
        
        async with httpx.AsyncClient() as client:
            # Verify API is running
            try:
                health = await client.get(f"{self.base_url}/health", timeout=5.0)
                if health.status_code != 200:
                    print("❌ ERROR: API health check failed")
                    return False
            except Exception as e:
                print(f"❌ ERROR: Could not connect to API at {self.base_url}")
                print(f"   Make sure the server is running: python -m uvicorn app.main:app --reload")
                return False
            
            print("✓ API health check passed")
            print()
            
            # Run tests
            print("Running latency tests...")
            print("-" * 80)
            
            for i, query in enumerate(queries, 1):
                result = await self.test_single_query(client, query)
                self.results.append(result)
                
                status_icon = "✓" if result["under_sla"] else "✗"
                print(
                    f"[{i:2d}/{len(queries)}] {status_icon} "
                    f"{result['response_time_ms']:7.2f}ms | "
                    f"{query[:50]:<50}"
                )
        
        return True
    
    def print_summary(self):
        """Print test summary"""
        if not self.results:
            print("No test results available")
            return
        
        successful = [r for r in self.results if r["status"] == "success"]
        times_ms = [r["response_time_ms"] for r in self.results]
        sla_passed = sum(1 for r in self.results if r["under_sla"])
        
        print()
        print("=" * 80)
        print("LATENCY TEST SUMMARY")
        print("=" * 80)
        
        print(f"\nTest Results:")
        print(f"  Total queries: {len(self.results)}")
        print(f"  Successful: {len(successful)}/{len(self.results)}")
        print(f"  SLA compliance: {sla_passed}/{len(self.results)} ({sla_passed/len(self.results)*100:.1f}%)")
        
        if successful:
            exec_times = [r["response_time_ms"] for r in self.results]
            
            print(f"\nLatency Statistics (ms):")
            print(f"  Min:     {min(exec_times):7.2f}")
            print(f"  Max:     {max(exec_times):7.2f}")
            print(f"  Mean:    {statistics.mean(exec_times):7.2f}")
            print(f"  Median:  {statistics.median(exec_times):7.2f}")
            print(f"  Std Dev: {statistics.stdev(exec_times) if len(exec_times) > 1 else 0:7.2f}")
            
            # Calculate percentiles
            sorted_times = sorted(exec_times)
            p50 = sorted_times[int(len(sorted_times) * 0.50)]
            p95 = sorted_times[int(len(sorted_times) * 0.95)]
            p99 = sorted_times[int(len(sorted_times) * 0.99)]
            
            print(f"\nPercentiles (ms):")
            print(f"  P50 (median): {p50:7.2f}")
            print(f"  P95:         {p95:7.2f}")
            print(f"  P99:         {p99:7.2f}")
            print(f"  SLA ({self.sla_ms}ms): {p95:.2f} {'✓ PASS' if p95 <= self.sla_ms else '✗ FAIL'}")
        
        # Error summary
        errors = [r for r in self.results if r["status"] != "success"]
        if errors:
            print(f"\nErrors ({len(errors)}):")
            error_types = {}
            for error in errors:
                status = error["status"]
                error_types[status] = error_types.get(status, 0) + 1
            
            for error_type, count in error_types.items():
                print(f"  {error_type}: {count}")
        
        print("=" * 80)
    
    def export_results(self, output_file: str = "latency_test_results.json"):
        """Export test results to JSON"""
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Calculate statistics
        successful = [r for r in self.results if r["status"] == "success"]
        times_ms = [r["response_time_ms"] for r in successful]
        
        output_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "configuration": {
                "api_url": self.base_url,
                "sla_ms": self.sla_ms,
                "queries_count": len(self.results)
            },
            "summary": {
                "total_tests": len(self.results),
                "successful": len(successful),
                "sla_compliance": sum(1 for r in self.results if r["under_sla"]) / len(self.results) * 100 if self.results else 0,
                "min_ms": min(times_ms) if times_ms else 0,
                "max_ms": max(times_ms) if times_ms else 0,
                "mean_ms": statistics.mean(times_ms) if times_ms else 0,
                "median_ms": statistics.median(times_ms) if times_ms else 0,
                "p95_ms": sorted(times_ms)[int(len(times_ms) * 0.95)] if len(times_ms) > 1 else 0,
                "p99_ms": sorted(times_ms)[int(len(times_ms) * 0.99)] if len(times_ms) > 1 else 0
            },
            "results": self.results
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\n✓ Results exported to {output_file}")


async def main():
    """Main latency testing entry point"""
    tester = LatencyTester(sla_ms=800)
    
    # Run tests
    success = await tester.run_latency_tests()
    
    if success:
        # Print summary
        tester.print_summary()
        
        # Export results
        tester.export_results("profiles/latency_test_results.json")


if __name__ == "__main__":
    asyncio.run(main())
