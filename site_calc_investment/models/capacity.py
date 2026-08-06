"""Capacity-reservation models and per-device investment accounting."""

from typing import List, Literal, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CapacityTariff(BaseModel):
    """One entry of a capacity-charge price menu.

    Per billing period the charge is ``fixed_price + reserved_price * R +
    peak_price * peak``, where ``R`` is the reserved capacity and ``peak``
    the period's measured peak flow. With several tariffs on one
    reservation, the cheapest tariff is applied automatically each period.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Tariff label (e.g. 'T1'); reported back in results")
    reserved_price: float = Field(..., ge=0, description="EUR per MW of reserved capacity R, per billing period")
    peak_price: float = Field(..., ge=0, description="EUR per MW of the period's measured peak")
    fixed_price: float = Field(0.0, ge=0, description="Fixed EUR per billing period when this tariff is selected")


class CapacityReservation(BaseModel):
    """Reserved-capacity limit and charge on a device flow.

    The watched flow can never exceed the reserved capacity ``R``; every
    billing period intersecting the optimization horizon is billed in
    full. ``R`` is either contracted (``reserved`` set) or sized by the
    optimizer within ``[min_reserved, max_reserved]``.
    """

    model_config = ConfigDict(extra="forbid")

    periods: Literal["calendar_month", "calendar_year", "horizon"] = Field(
        ...,
        description=(
            "Billing period split. Use 'horizon' for one-shot sizing (CAPEX), "
            "'calendar_month' for monthly grid capacity tariffs"
        ),
    )
    tariffs: List[CapacityTariff] = Field(
        default_factory=list, max_length=50, description="Price menu; empty list declares an unpriced pure limit"
    )
    reserved: Optional[float] = Field(
        None, ge=0, description="Fixed contracted capacity (MW); None lets the optimizer size R"
    )
    min_reserved: float = Field(0.0, ge=0, description="Lower bound for an optimized R (MW)")
    max_reserved: Optional[float] = Field(
        None, gt=0, description="Upper bound for R (MW); defaults to the device's maximum flow"
    )
    timezone: Optional[str] = Field(None, description="IANA billing timezone, e.g. 'Europe/Prague'")

    @model_validator(mode="after")
    def validate_reservation(self) -> "CapacityReservation":
        """Enforce consistency between reserved value, bounds, and tariffs."""
        if self.reserved is None and (not self.tariffs or any(t.reserved_price <= 0 for t in self.tariffs)):
            raise ValueError(
                "optimizing reserved capacity requires at least one tariff and every tariff to have reserved_price > 0"
            )
        if self.max_reserved is not None and self.min_reserved > self.max_reserved:
            raise ValueError("min_reserved cannot exceed max_reserved")
        if self.reserved is not None:
            if self.reserved < self.min_reserved:
                raise ValueError("reserved cannot be below min_reserved")
            if self.max_reserved is not None and self.reserved > self.max_reserved:
                raise ValueError("reserved cannot exceed max_reserved")
        if self.timezone is not None:
            try:
                ZoneInfo(self.timezone)
            except Exception as e:
                raise ValueError(f"invalid timezone {self.timezone!r}: {e}") from e
        return self


class DeviceInvestment(BaseModel):
    """Fixed accounting costs for client-side NPV/IRR analysis.

    These values are never sent to the server and never influence the
    optimization. Use sizing reservations (e.g. a battery's power_sizing)
    for capacity costs the optimizer should trade off.
    """

    model_config = ConfigDict(extra="forbid")

    capital_cost: Optional[float] = Field(None, ge=0, description="One-time investment cost (EUR)")
    annual_opex: Optional[float] = Field(None, ge=0, description="Fixed operation and maintenance cost (EUR/year)")
