"""Version 1 contracts shared with the desktop client."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NextAction = Literal["open_ct_import", "open_annulus_plane", "open_measurement"]


class SoftwareState(BaseModel):
    """A client-owned snapshot; omitted fields use conservative defaults."""

    model_config = ConfigDict(strict=True, extra="forbid")

    current_page: str = Field(default="home", min_length=1, max_length=128)
    ct_loaded: bool = False
    annulus_plane_confirmed: bool = False
    measurement_completed: bool = False


class GuideRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    state: SoftwareState


class GuideResponse(BaseModel):
    message: str
    next_action: NextAction | None = None
