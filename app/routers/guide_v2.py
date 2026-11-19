"""Bounded V2 transport and errors, isolated from V1."""
import json
import logging
import re
import time
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from app.models.schemas_v2 import GuideRequest, GuideResponse
from app.models.invariants_v2 import invariant_failure
from app.services.guidance_v2 import generate_guidance

router = APIRouter()
logger = logging.getLogger(__name__)
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
MESSAGES = {"INVALID_JSON": "请求不是有效的 JSON 对象。", "INVALID_REQUEST": "请求字段不符合接口约定。", "INCONSISTENT_STATE": "请求状态不一致。", "UNSUPPORTED_MEDIA_TYPE": "请求媒体类型或编码不受支持。", "REQUEST_TOO_LARGE": "请求体过大。", "INTERNAL_ERROR": "引导服务内部错误。"}

def reject_constant(value):
    raise ValueError("Nonfinite number")

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate key")
        result[key] = value
    return result

def details_for(error):
    result = set()
    for e in error.errors(include_input=False, include_url=False):
        kind, loc = e["type"], list(e["loc"])
        if kind == "extra_forbidden": loc = loc[:-1]
        if loc and loc[0] == "supported_actions": loc = loc[:1]
        path = ".".join(str(p) for p in loc) or "$"
        if kind == "missing": code = "MISSING_FIELD"
        elif kind == "extra_forbidden": code = "UNKNOWN_FIELD"
        elif kind == "literal_error": code = "INVALID_ENUM"
        elif kind == "duplicate_item": code = "DUPLICATE_ITEM"
        elif kind in ("string_pattern_mismatch",): code = "INVALID_FORMAT"
        elif kind in ("greater_than_equal", "less_than_equal", "string_too_short", "string_too_long", "too_long"): code = "OUT_OF_RANGE"
        else: code = "INVALID_TYPE"
        result.add((path, code))
    return [{"field": p, "code": c} for p, c in sorted(result)[:32]]

def request_schema():
    schema = GuideRequest.model_json_schema()
    definitions = schema.pop("$defs", {})
    def inline(value):
        if isinstance(value, dict):
            if "$ref" in value and value["$ref"].startswith("#/$defs/"):
                return inline(definitions[value["$ref"].split("/")[-1]])
            return {key: inline(item) for key, item in value.items()}
        if isinstance(value, list):
            return [inline(item) for item in value]
        return value
    return inline(schema)

@router.post("/api/v2/agent/guide", response_model=GuideResponse,
    openapi_extra={"requestBody": {"required": True, "content": {"application/json": {"schema": request_schema()}}}},
    responses={code: {"description": text} for code, text in {413: "Request too large", 415: "Unsupported media type", 422: "Invalid request or inconsistent state", 500: "Internal error"}.items()})
async def guide_v2(request: Request):
    started = time.perf_counter()
    rid = None
    status = 500
    reason = "INTERNAL_ERROR"
    def failure(http_status, code, details=None):
        nonlocal status, reason
        status, reason = http_status, code
        return JSONResponse(status_code=status, content={"protocol_version": "2.1", "request_id": rid,
            "error": {"code": code, "message": MESSAGES[code], "details": details or []}})
    try:
        media = request.headers.get("content-type", "").lower().split(";")
        if media[0].strip() != "application/json" or request.headers.get("content-encoding") or any(
            p.strip().replace(" ", "") not in ('charset=utf-8', 'charset="utf-8"') for p in media[1:]):
            return failure(415, "UNSUPPORTED_MEDIA_TYPE")
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 16384:
                return failure(413, "REQUEST_TOO_LARGE")
            body.extend(chunk)
        try:
            data = json.loads(body.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)
        except (ValueError, UnicodeError, RecursionError):
            return failure(422, "INVALID_JSON", [{"code": "INVALID_JSON", "field": "$"}])
        if isinstance(data, dict) and isinstance(data.get("request_id"), str) and UUID.fullmatch(data["request_id"]):
            rid = data["request_id"]
        try:
            model = GuideRequest.model_validate(data)
        except ValidationError as exc:
            return failure(422, "INVALID_REQUEST", details_for(exc))
        invariant = invariant_failure(model.state.model_dump())
        if invariant:
            return failure(422, "INCONSISTENT_STATE", [{"code": "INCONSISTENT_STATE", "field": invariant[1]}])
        response = generate_guidance(model)
        status, reason = 200, response.reason_code
        return response
    except Exception:
        logger.exception("V2 internal error request_id=%s", rid)
        return failure(500, "INTERNAL_ERROR")
    finally:
        logger.info("guidance", extra={"request_id": rid, "protocol_version": "2.1", "rule_version": "rcviplan-prompts/2.1.0", "elapsed_ms": round((time.perf_counter()-started)*1000, 2), "http_status": status, "reason_code": reason})
