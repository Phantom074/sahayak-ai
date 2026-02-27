"""
Observability instrumentation for all Sahayak services.
Provides structured logging, X-Ray tracing, and CloudWatch metrics.
"""
import json
import time
import boto3
import logging
from functools import wraps
from typing import Callable

try:
    from aws_xray_sdk.core import xray_recorder, patch_all
    patch_all()
    XRAY_ENABLED = True
except ImportError:
    XRAY_ENABLED = False

import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()
_cw_client = None


def _get_cloudwatch():
    global _cw_client
    if _cw_client is None:
        _cw_client = boto3.client("cloudwatch", region_name="ap-south-1")
    return _cw_client


def emit_metric(name: str, value: float, service: str, unit: str = "Count", dimensions: dict = None):
    """Emit CloudWatch custom metric. Non-blocking."""
    try:
        dims = [
            {"Name": "ServiceName", "Value": service},
            {"Name": "Environment", "Value": "prod"},
        ]
        if dimensions:
            dims.extend([{"Name": k, "Value": v} for k, v in dimensions.items()])
        _get_cloudwatch().put_metric_data(
            Namespace="Sahayak/Services",
            MetricData=[{"MetricName": name, "Value": value, "Unit": unit, "Dimensions": dims}],
        )
    except Exception:
        pass  # Never break happy path for metrics


def instrument_handler(service_name: str, operation: str):
    """Lambda handler decorator: adds timing, logging, X-Ray, and CloudWatch metrics."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(event, context):
            start_time = time.time()
            session_id = event.get("pathParameters", {}).get("session_id", "none")
            req_id = getattr(context, "aws_request_id", "local")

            log = logger.bind(service=service_name, operation=operation,
                              session_id=session_id, request_id=req_id)

            segment_name = f"{service_name}.{operation}"
            try:
                if XRAY_ENABLED:
                    with xray_recorder.in_segment(segment_name):
                        result = func(event, context)
                else:
                    result = func(event, context)

                duration_ms = (time.time() - start_time) * 1000
                log.info("handler_success", duration_ms=round(duration_ms, 2),
                         status_code=result.get("statusCode", 200))

                emit_metric("SuccessfulRequests", 1, service_name)
                emit_metric("RequestDuration", duration_ms, service_name, "Milliseconds")
                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                log.error("handler_error", error=str(e), error_type=type(e).__name__,
                          duration_ms=round(duration_ms, 2))
                emit_metric("FailedRequests", 1, service_name)
                raise
        return wrapper
    return decorator
