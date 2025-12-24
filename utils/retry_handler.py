import asyncio
import time
from typing import Callable, Any, Optional
from functools import wraps
from utils.logger import logger


class CircuitBreaker:
    """Circuit breaker for external API calls"""

    def __init__(self, failure_threshold: int = 5, timeout_duration: int = 60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout_duration = timeout_duration
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""

        # If circuit is OPEN, check if timeout has passed
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout_duration:
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker transitioning to HALF_OPEN")
            else:
                raise Exception(f"Circuit breaker is OPEN - service unavailable")

        try:
            result = func(*args, **kwargs)

            # Success - reset failure count
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                logger.info("Circuit breaker reset to CLOSED")
            self.failure_count = 0

            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            # Open circuit if threshold exceeded
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.error(
                    "Circuit breaker OPENED",
                    failure_count=self.failure_count,
                    threshold=self.failure_threshold,
                )

            raise


# Global circuit breakers
confluence_breaker = CircuitBreaker(failure_threshold=3, timeout_duration=60)
odoo_breaker = CircuitBreaker(failure_threshold=5, timeout_duration=30)


def retry_on_network_error(
    max_attempts: int = 2, delay_seconds: int = 30, timeout_seconds: int = 120
):
    """
    Retry decorator for network errors only.

    Per spec (WithoutTextractContext.txt:1714-1719):
    - Only retry on network/timeout errors
    - NO retries on deterministic validation failures
    - Max 1 retry with 30s delay
    - Total timeout ~120s (platform limit)
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            last_exception = None

            for attempt in range(max_attempts):
                # Check platform timeout
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    logger.error(
                        "Platform timeout exceeded",
                        elapsed_seconds=elapsed,
                        timeout_limit=timeout_seconds,
                    )
                    raise TimeoutError(
                        f"Operation exceeded {timeout_seconds}s platform limit"
                    )

                try:
                    logger.info(
                        f"Attempting {func.__name__}",
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                    )

                    result = (
                        await func(*args, **kwargs)
                        if asyncio.iscoroutinefunction(func)
                        else func(*args, **kwargs)
                    )

                    logger.info(f"{func.__name__} succeeded", attempt=attempt + 1)
                    return result

                except (ConnectionError, TimeoutError, OSError) as e:
                    # Network errors - retry eligible
                    last_exception = e
                    logger.warning(
                        f"{func.__name__} network error",
                        attempt=attempt + 1,
                        error=str(e),
                        will_retry=attempt < max_attempts - 1,
                    )

                    if attempt < max_attempts - 1:
                        await asyncio.sleep(delay_seconds)

                except (ValueError, KeyError, AttributeError) as e:
                    # Deterministic errors - NO retry
                    logger.error(
                        f"{func.__name__} validation error - no retry", error=str(e)
                    )
                    raise

                except Exception as e:
                    # Unknown errors - log and re-raise
                    logger.error(f"{func.__name__} unexpected error", error=str(e))
                    raise

            # All retries exhausted
            logger.error(
                f"{func.__name__} failed after all retries", attempts=max_attempts
            )
            raise last_exception

        return wrapper

    return decorator
