"""Deterministic software navigation rules, not clinical recommendations."""

from app.models.schemas import GuideResponse, SoftwareState


def generate_guidance(state: SoftwareState) -> GuideResponse:
    """Return the first unmet prerequisite, even for inconsistent snapshots."""
    if not state.ct_loaded:
        return GuideResponse(message="请先导入 CT 影像。", next_action="open_ct_import")
    if not state.annulus_plane_confirmed:
        return GuideResponse(
            message="请进入瓣环定位模块。", next_action="open_annulus_plane"
        )
    if not state.measurement_completed:
        return GuideResponse(message="请进入瓣环测量模块。", next_action="open_measurement")
    return GuideResponse(message="示例规划步骤已完成。", next_action=None)
