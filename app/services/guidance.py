"""Deterministic software navigation rules, not clinical recommendations."""

from app.models.schemas import GuideResponse, SoftwareState


def _navigation_guidance(state: SoftwareState) -> GuideResponse:
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


def generate_guidance(state: SoftwareState) -> GuideResponse:
    """Add segmentation observations without blocking the existing navigation."""
    guidance = _navigation_guidance(state)
    if not state.ct_loaded or state.segmentation_status is None:
        return guidance
    messages = {
        "not_started": "尚未启动分割，可在分割页面开始操作。",
        "running": "分割正在进行，请等待结果。",
        "succeeded": (
            "分割已完成，请查看血管模型。"
            if state.segmentation_result_available
            else "分割任务已结束，但尚无可用结果，请在软件中核对。"
        ),
        "failed": (
            "本次分割失败，请查看软件错误提示。已有可用分割结果，请核对后使用。"
            if state.segmentation_result_available
            else "本次分割失败，尚无可用结果，请查看软件错误提示并处理后重试。"
        ),
    }
    return GuideResponse(
        message=messages[state.segmentation_status] + "\n\n" + guidance.message,
        next_action=guidance.next_action,
    )
