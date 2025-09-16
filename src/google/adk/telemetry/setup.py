# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Optional

from opentelemetry import _logs
from opentelemetry import metrics
from opentelemetry import trace
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs import LogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader
from opentelemetry.sdk.resources import OTELResourceDetector
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.sdk.trace import TracerProvider

from ..utils.feature_decorator import experimental


@dataclass
class OTelHooks:
  span_processors: list[SpanProcessor] = field(default_factory=list)
  metric_readers: list[MetricReader] = field(default_factory=list)
  log_record_processors: list[LogRecordProcessor] = field(default_factory=list)


@experimental()
def maybe_set_otel_providers(
    otel_hooks_to_setup: list[OTelHooks] = None,
    otel_resource: Optional[Resource] = None,
):
  """Sets up OTel providers if hooks for a given telemetry type were
  passed.

  If a provider for a specific telemetry type was already globally set -
  this function will not override it or register more exporters.

  Args:
    otel_hooks_to_setup: per-telemetry-type processors and readers to be added
    to OTel providers. If no hooks for a specific telemetry type are passed -
    provider will not be set.
    otel_resource: OTel resource to use in providers.
    If empty - default OTel resource detection will be used.
  """
  if otel_hooks_to_setup is None:
    otel_hooks_to_setup = []
  if otel_resource is None:
    otel_resource = _get_otel_resource()

  span_processors = []
  metric_readers = []
  log_record_processors = []
  for otel_hooks in otel_hooks_to_setup:
    for span_processor in otel_hooks.span_processors:
      span_processors.append(span_processor)
    for metric_reader in otel_hooks.metric_readers:
      metric_readers.append(metric_reader)
    for log_record_processor in otel_hooks.log_record_processors:
      log_record_processors.append(log_record_processor)

  # Try to set up OTel tracing.
  # If the TracerProvider was already set outside of ADK, this would be a no-op
  # and results in a warning. In such case we rely on user setup.
  if span_processors:
    new_tracer_provider = TracerProvider(resource=otel_resource)
    for exporter in span_processors:
      new_tracer_provider.add_span_processor(exporter)
    trace.set_tracer_provider(new_tracer_provider)

  # Try to set up OTel metrics.
  # If the MeterProvider was already set outside of ADK, this would be a no-op
  # and results in a warning. In such case we rely on user setup.
  if metric_readers:
    metrics.set_meter_provider(
        MeterProvider(
            metric_readers=metric_readers,
            resource=otel_resource,
        )
    )

  # Try to set up OTel logging.
  # If the LoggerProvider was already set outside of ADK, this would be a no-op
  # and results in a warning. In such case we rely on user setup.
  if log_record_processors:
    new_logger_provider = LoggerProvider(
        resource=otel_resource,
    )
    for exporter in log_record_processors:
      new_logger_provider.add_log_record_processor(exporter)
    _logs.set_logger_provider(new_logger_provider)


def _get_otel_resource() -> Resource:
  # The OTELResourceDetector populates resource labels from
  # environment variables like OTEL_SERVICE_NAME and OTEL_RESOURCE_ATTRIBUTES.
  return OTELResourceDetector().detect()
