"""Planning hints 2.1.0: existing operations only."""
import math
from typing import Annotated, Literal
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

def json_integer(value):
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    return value

Revision = Annotated[int, Field(ge=0, le=9007199254740991), BeforeValidator(json_integer)]
Uuid = Annotated[str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")]
Target = Literal["segment.auto_segment", "nav.next", "nav.back", "annulus.pick", "navigation.sent_setting", "navigation.sent_move", "navigation.sent_return"]
Reason = Literal["CT_REQUIRED", "SEGMENT_START", "SEGMENT_RUNNING", "SEGMENT_FAILED", "SEGMENT_AVAILABLE", "PICK_POINTS", "POINTS_COMPLETE", "RETURN_TO_POINTS", "SET_PROSTHESIS", "CHECK_PROSTHESIS", "MOVE_PROSTHESIS", "MOVING_PROSTHESIS", "PROSTHESIS_RETURNED", "ENTER_SEGMENTATION", "NO_GUIDANCE"]

class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

class WorkflowState(StrictModel):
    current_page: Literal["render", "vessel_extract", "annulus_pick", "navigation", "reserved_4", "reserved_5"]
    ct_loaded: bool
    picked_point_count: Annotated[int, Field(ge=0, le=3), BeforeValidator(json_integer)]
    segmentation_status: Literal["not_started", "running", "succeeded", "failed"]
    segmentation_result_available: bool
    prosthesis_status: Literal["absent", "unknown", "available"]
    move_enabled: bool
    returned: bool

class GuideRequest(StrictModel):
    protocol_version: Literal["2.1"]
    request_id: Uuid
    state_revision: Revision
    state: WorkflowState

class GuideResponse(StrictModel):
    protocol_version: Literal["2.1"]
    request_id: Uuid
    state_revision: Revision
    rule_version: Literal["rcviplan-prompts/2.1.0"]
    reason_code: Reason
    message: Annotated[str, Field(min_length=1, max_length=1024)]
    target_id: Target | None
