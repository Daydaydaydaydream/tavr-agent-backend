"""Cross-field checks for the reduced planning snapshot."""
def invariant_failure(s):
    if not s["ct_loaded"] and (s["picked_point_count"] or s["prosthesis_status"] != "absent" or s["segmentation_status"] != "not_started" or s["segmentation_result_available"]):
        return "I01", "state.ct_loaded"
    if s["segmentation_status"] == "succeeded" and not s["segmentation_result_available"]:
        return "I02", "state.segmentation_result_available"
    if (s["move_enabled"] or s["returned"]) and (s["prosthesis_status"] != "available" or s["picked_point_count"] != 3):
        return "I03", "state.prosthesis_status"
    return None
