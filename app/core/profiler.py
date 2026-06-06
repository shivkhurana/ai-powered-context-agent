"""
Performance profiling and latency optimization utilities
Tracks execution time across different components to identify bottlenecks
"""

import time
import logging
from typing import Dict, List, Callable, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class LatencyData:
    """Stores latency information for a query"""
    query: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_execution_ms: float = 0.0
    cache_lookup_ms: float = 0.0
    embedding_ms: float = 0.0
    retrieval_ms: float = 0.0
    llm_call_ms: float = 0.0
    response_parsing_ms: float = 0.0
    under_sla: bool = False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        return d


class LatencyProfiler:
    """Profiles latency across query execution"""
    
    def __init__(self, sla_ms: float = 800.0):
        self.sla_ms = sla_ms
        self.latencies: List[LatencyData] = []
        self.lock_profiling = False
    
    def start_profile(self, query: str) -> LatencyData:
        """Start latency profiling for a query"""
        return LatencyData(query=query)
    
    def record_latency(self, data: LatencyData):
        """Record latency data"""
        # Calculate total execution time
        data.total_execution_ms = (
            data.cache_lookup_ms +
            data.embedding_ms +
            data.retrieval_ms +
            data.llm_call_ms +
            data.response_parsing_ms
        )
        
        # Check if under SLA
        data.under_sla = data.total_execution_ms <= self.sla_ms
        
        self.latencies.append(data)
        
        if not data.under_sla:
            logger.warning(
                f"Query '{data.query[:50]}' exceeded SLA: "
                f"{data.total_execution_ms:.2f}ms > {self.sla_ms}ms"
            )
    
    def get_statistics(self) -> Dict:
        """Get latency statistics"""
        if not self.latencies:
            return {
                "total_queries": 0,
                "average_latency_ms": 0,
                "min_latency_ms": 0,
                "max_latency_ms": 0,
                "sla_compliance": 0.0,
                "p50_ms": 0,
                "p95_ms": 0,
                "p99_ms": 0
            }
        
        latencies_ms = [l.total_execution_ms for l in self.latencies]
        latencies_ms.sort()
        
        sla_compliant = sum(1 for l in self.latencies if l.under_sla)
        
        return {
            "total_queries": len(self.latencies),
            "average_latency_ms": sum(latencies_ms) / len(latencies_ms),
            "min_latency_ms": min(latencies_ms),
            "max_latency_ms": max(latencies_ms),
            "sla_compliance": (sla_compliant / len(self.latencies)) * 100,
            "p50_ms": latencies_ms[len(latencies_ms) // 2],
            "p95_ms": latencies_ms[int(len(latencies_ms) * 0.95)],
            "p99_ms": latencies_ms[int(len(latencies_ms) * 0.99)]
        }
    
    def export_latencies(self, output_file: str):
        """Export latency data to JSON file"""
        try:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "generated": datetime.utcnow().isoformat(),
                "sla_ms": self.sla_ms,
                "statistics": self.get_statistics(),
                "latencies": [l.to_dict() for l in self.latencies]
            }
            
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Exported latency data to {output_file}")
        except Exception as e:
            logger.error(f"Error exporting latency data: {e}")
    
    def clear(self):
        """Clear collected latency data"""
        self.latencies.clear()


class TimerContext:
    """Context manager for timing code blocks"""
    
    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.elapsed_ms = 0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed_ms = (time.time() - self.start_time) * 1000
        logger.debug(f"{self.name}: {self.elapsed_ms:.2f}ms")


# Global profiler instance
_profiler: LatencyProfiler = LatencyProfiler()


def get_profiler() -> LatencyProfiler:
    """Get global profiler instance"""
    return _profiler


def timer(name: str) -> TimerContext:
    """Create a timer context"""
    return TimerContext(name)


async def measure_async(coro: Any, name: str) -> tuple:
    """Measure async function execution time"""
    start_time = time.time()
    result = await coro
    elapsed_ms = (time.time() - start_time) * 1000
    logger.debug(f"{name}: {elapsed_ms:.2f}ms")
    return result, elapsed_ms
