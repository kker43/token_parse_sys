"""Deterministic readiness checks for published factual products."""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.contracts import DataProductContract, DataQualityStatus


@dataclass(frozen=True, slots=True)
class DataProductReadinessInputs:
    """Observed evidence used to validate a product/date for downstream use."""

    requested_date: str
    observed_dates: frozenset[str] = field(default_factory=frozenset)
    observed_non_null_fields: frozenset[str] = field(default_factory=frozenset)
    observed_data_version: str | None = None
    observed_record_count: int | None = None


@dataclass(frozen=True, slots=True)
class DataProductReadinessResult:
    """Structured readiness decision for one product/date."""

    data_product: str
    requested_date: str
    ready: bool
    reasons: tuple[str, ...]
    quality_status: DataQualityStatus | None = None


class DataProductReadinessChecker:
    """Validate whether a published product/date is safe for downstream consumption."""

    def check(
        self,
        contract: DataProductContract,
        quality_status: DataQualityStatus | None,
        inputs: DataProductReadinessInputs,
    ) -> DataProductReadinessResult:
        """Evaluate one product/date using only deterministic evidence."""

        reasons: list[str] = []

        if quality_status is None:
            reasons.append("missing_quality_status")
            return DataProductReadinessResult(
                data_product=contract.name,
                requested_date=inputs.requested_date,
                ready=False,
                reasons=tuple(reasons),
                quality_status=None,
            )

        if quality_status.data_product != contract.name:
            reasons.append("quality_status_product_mismatch")

        if quality_status.data_date != inputs.requested_date:
            reasons.append("quality_status_date_mismatch")

        if not quality_status.is_consumable(contract.allowed_statuses, contract.allowed_quality_levels):
            reasons.append("quality_gate_blocked")

        if quality_status.record_count < quality_status.expected_min_records:
            reasons.append("record_count_below_expected_min")

        if inputs.observed_record_count is not None and inputs.observed_record_count != quality_status.record_count:
            reasons.append("record_count_mismatch")

        if inputs.observed_dates and inputs.requested_date not in inputs.observed_dates:
            reasons.append("requested_date_not_present_in_observed_data")

        if inputs.observed_data_version is not None and inputs.observed_data_version != contract.data_version:
            reasons.append("data_version_mismatch")

        required_fields = set(contract.required_non_nullable_fields())
        if required_fields:
            missing_fields = sorted(required_fields.difference(inputs.observed_non_null_fields))
            if missing_fields:
                reasons.append(f"missing_non_null_fields:{','.join(missing_fields)}")

        return DataProductReadinessResult(
            data_product=contract.name,
            requested_date=inputs.requested_date,
            ready=not reasons,
            reasons=tuple(reasons),
            quality_status=quality_status,
        )
