"""Page-local rules. No navigation, model invocation or business mutation."""
from app.models.schemas_v2 import GuideRequest, GuideResponse

def choose(s):
    if not s.ct_loaded:
        return "CT_REQUIRED", "请从主程序打开有效 CT 病例。", None
    if s.current_page == "vessel_extract":
        if s.segmentation_status == "running":
            return "SEGMENT_RUNNING", "正在分割，请等待；也可继续取点。", None
        if s.segmentation_status == "failed":
            suffix = "已有分割结果仍可查看。" if s.segmentation_result_available else ""
            return "SEGMENT_FAILED", "本次分割失败，可查看软件错误提示后重试，也可继续取点。" + suffix, "segment.auto_segment"
        if s.segmentation_result_available:
            return "SEGMENT_AVAILABLE", "可查看分割结果，继续进行三点取点。", "nav.next"
        return "SEGMENT_START", "可先进行血管分割，也可继续取点。", "segment.auto_segment"
    if s.current_page == "annulus_pick":
        if s.picked_point_count < 3:
            return "PICK_POINTS", f"已选取 {s.picked_point_count} 个点，请继续选取剩余 {3-s.picked_point_count} 个点。", "annulus.pick"
        return "POINTS_COMPLETE", "已完成三点取点，请检查点位后进入假体设置；需要调整时可删除重取。", "nav.next"
    if s.current_page == "navigation":
        if s.picked_point_count < 3:
            return "RETURN_TO_POINTS", "请返回取点页完成三点取点。", "nav.back"
        if s.prosthesis_status == "absent":
            return "SET_PROSTHESIS", "请打开假体设置，配置参数并应用。", "navigation.sent_setting"
        if s.prosthesis_status == "unknown":
            return "CHECK_PROSTHESIS", "请检查假体模型、点位与参数；当前尚不能确认假体可操作。", None
        if s.returned:
            return "PROSTHESIS_RETURNED", "已执行回位，可继续检查位置或调整参数。", None
        if s.move_enabled:
            return "MOVING_PROSTHESIS", "可调整假体位置，需要恢复时使用回位。", "navigation.sent_return"
        return "MOVE_PROSTHESIS", "可检查假体位置，按需移动；需要恢复时使用回位。", "navigation.sent_move"
    if s.current_page == "render":
        return "ENTER_SEGMENTATION", "可进入血管分割页面开始规划。", "nav.next"
    return "NO_GUIDANCE", "当前页面暂无操作提示。", None

def generate_guidance(request: GuideRequest) -> GuideResponse:
    reason, message, target = choose(request.state)
    return GuideResponse(protocol_version="2.1", request_id=request.request_id,
        state_revision=request.state_revision, rule_version="rcviplan-prompts/2.1.0",
        reason_code=reason, message=message, target_id=target)
