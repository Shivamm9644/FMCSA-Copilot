"""
File: apps/parser/models.py
Why it exists:
    Provides strongly-typed Python dataclasses that represent parsed segments from the FMCSA ELD CSV file.
    By inheriting from DictLikeMixin, these dataclasses also support dictionary-like lookup operations
    (.get(), dictionary indexing), ensuring full compatibility with downstream validation agents
    and serializers that expect dictionaries.

Inputs:
    - Raw field values parsed from CSV rows.

Outputs:
    - Strongly-typed, dictionary-compatible model records for each ELD segment.

Dependencies:
    - dataclasses (Python Standard Library)
    - datetime (Python Standard Library)
    - decimal (Python Standard Library)
    - typing (Python Standard Library)
"""

from dataclasses import dataclass, asdict, fields
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, KeysView

class DictLikeMixin:
    """
    A mixin that allows dataclasses to be accessed like dictionaries.
    This provides backward/forward compatibility with validation agents and serializer code.
    """
    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def keys(self) -> KeysView[str]:
        return {f.name for f in fields(self)}.keys()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ELDHeaderRecord(DictLikeMixin):
    """
    Typed model for the ELD File Header segment.
    """
    eld_registration_id: str
    driver_last_name: str
    driver_first_name: str
    driver_username: str
    co_driver_last_name: str
    co_driver_first_name: str
    co_driver_username: str
    carrier_usdot: str
    carrier_name: str
    multi_day_basis: int
    start_hour: int
    shipping_doc: str
    exempt_status: str

@dataclass
class UserRecord(DictLikeMixin):
    """
    Typed model for users listed in the ELD User List section.
    """
    username: str
    last_name: str
    first_name: str
    license_state: str
    license_number: str

@dataclass
class CMVRecord(DictLikeMixin):
    """
    Typed model for commercial motor vehicles (CMVs) listed in the ELD CMV section.
    """
    power_unit_number: str
    vin: str
    license_plate_state: str
    license_plate: str

@dataclass
class ELDEventRecord(DictLikeMixin):
    """
    Typed model for individual telemetric logs inside the ELD Event List section.
    """
    sequence_id: int
    record_status: int
    record_origin: int
    event_type: int
    event_code: int
    event_date_time: datetime
    accumulated_engine_hours: Optional[Decimal]
    elapsed_miles: Optional[int]
    location_desc: str
    latitude: Optional[Decimal]
    longitude: Optional[Decimal]
    cmv_id: str
    cmv_vin: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["event_date_time"] = self.event_date_time.isoformat()
        if self.accumulated_engine_hours is not None:
            data["accumulated_engine_hours"] = float(self.accumulated_engine_hours)
        if self.latitude is not None:
            data["latitude"] = float(self.latitude)
        if self.longitude is not None:
            data["longitude"] = float(self.longitude)
        return data
