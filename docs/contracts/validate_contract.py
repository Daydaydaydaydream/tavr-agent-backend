"""Validate design artifacts only; never imports or runs the backend application.

Run with Python 3.12 and requirements-validation.txt installed in a separate env.
"""
from copy import deepcopy
from pathlib import Path
import json
import re

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate_spec

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent.parent / 'tests' / 'fixtures' / 'guide_v2'
VERSION = '2.0.0'
RULE_VERSION = 'rcviplan-guidance/1.0.0'
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')


def invariant_failure(state):
    """I01-I09, in normative order. Called only after structural validation."""
    s = state
    if s['ct_status'] != 'succeeded' and not (
        s['picked_point_count'] == 0 and s['prosthesis_status'] == 'absent'
        and s['segmentation_status'] == 'not_started'
        and not s['segmentation_result_available'] and s['save_status'] == 'not_started'
        and s['plan_revision'] == 0 and s['saved_plan_revision'] is None
    ):
        return 'I01', 'state.ct_status'
    for code, status, error in [('I02', 'segmentation_status', 'segmentation_error_code')]:
        if (s[status] == 'failed') != (s[error] is not None):
            return code, 'state.' + error
    if (s['segmentation_status'] == 'succeeded' and not s['segmentation_result_available']) or (
        s['segmentation_status'] == 'not_started' and s['segmentation_result_available']
    ):
        return 'I03', 'state.segmentation_result_available'
    if (s['prosthesis_status'] in ('ready', 'running', 'failed') and not (
        s['ct_status'] == 'succeeded' and s['picked_point_count'] == 3
    )) or (s['prosthesis_status'] == 'needs_reposition' and s['ct_status'] != 'succeeded'):
        return 'I04', 'state.prosthesis_status'
    if (s['prosthesis_status'] == 'failed') != (s['prosthesis_error_code'] is not None):
        return 'I05', 'state.prosthesis_error_code'
    if s['save_status'] in ('running', 'succeeded') and not (
        s['ct_status'] == 'succeeded' and s['picked_point_count'] == 3 and s['prosthesis_status'] == 'ready'
    ):
        return 'I06', 'state.save_status'
    if s['save_status'] == 'succeeded' and s['saved_plan_revision'] is None:
        return 'I07', 'state.saved_plan_revision'
    if (s['save_status'] == 'failed') != (s['save_error_code'] is not None):
        return 'I08', 'state.save_error_code'
    if s['saved_plan_revision'] is not None and s['saved_plan_revision'] > s['plan_revision']:
        return 'I09', 'state.saved_plan_revision'
    return None


def expected_notice_key(s):
    """A design checker for the decision table, not production guidance code."""
    if s['ct_status'] != 'succeeded':
        return {'not_started': 'CT_NOT_READY', 'running': 'CT_LOADING', 'failed': 'CT_LOAD_FAILED'}[s['ct_status']]
    if s['save_status'] == 'running':
        return 'PLAN_SAVING'
    if s['picked_point_count'] < 3:
        return 'POINTS_INCOMPLETE'
    if s['prosthesis_status'] != 'ready':
        return {'running': 'PROSTHESIS_BUILDING', 'failed': 'PROSTHESIS_FAILED', 'absent': 'PROSTHESIS_NOT_CREATED', 'needs_reposition': 'PROSTHESIS_NEEDS_REPOSITION'}[s['prosthesis_status']]
    if s['save_status'] == 'failed':
        return 'PLAN_SAVE_FAILED'
    if s['saved_plan_revision'] is None or s['saved_plan_revision'] != s['plan_revision']:
        return 'PLAN_UNSAVED'
    return 'PLAN_SAVED'


def main():
    spec = yaml.safe_load((HERE / 'guide-v2.openapi.yaml').read_text())
    assert spec == json.loads((HERE / 'guide-v2.openapi.json').read_text()), 'YAML/JSON drift'
    validate_spec(spec)
    assert spec['info']['version'] == VERSION
    rules = json.loads((HERE / 'guide-v2.decision-table.json').read_text())
    assert rules['contract_version'] == VERSION and rules['rule_version'] == RULE_VERSION
    components = spec['components']

    def validator(name, structural=False):
        c = deepcopy(components)
        if structural:
            c['schemas']['WorkflowState'].pop('allOf')
        schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema', '$ref': '#/components/schemas/' + name, 'components': c}
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, format_checker=FormatChecker())

    request_validator = validator('GuideRequest')
    structural_validator = validator('GuideRequest', True)
    response_validator = validator('GuideResponse')
    error_validator = validator('ErrorResponse')
    dataset = json.loads((FIXTURES / 'http-cases.json').read_text())
    assert dataset['contract_version'] == VERSION
    cases = dataset['cases']
    assert len({c['id'] for c in cases}) == len(cases)
    positives = negatives = 0
    coverage = set()
    invariant_coverage = set()
    alert_branches = set()
    rows = {r['reason_code']: r for r in rules['primary']}
    for c in cases:
        req, res = c['request'], c['expected_response']
        errors = list(structural_validator.iter_errors(req))
        inv = None if errors else invariant_failure(req['state'])
        if c['expected_status'] == 200:
            assert not errors and inv is None, (c['id'], errors, inv)
            request_validator.validate(req)
            response_validator.validate(res)
            assert res['request_id'] == req['request_id'] and res['state_revision'] == req['state_revision'], c['id']
            assert res['rule_version'] == RULE_VERSION
            key = expected_notice_key(req['state'])
            row = rows[key]
            coverage.add(key)
            assert res['reason_code'] == key, c['id']
            notices = [(row, res)]
            status = req['state']['segmentation_status']
            if status in ('running', 'failed'):
                index = 0 if status == 'running' else (2 if req['state']['segmentation_result_available'] else 1)
                alert_branches.add(index)
                assert len(res['alerts']) == 1, c['id']
                notices.append((rules['alerts'][index], res['alerts'][0]))
            else:
                assert res['alerts'] == [], c['id']
            for rule, actual in notices:
                n = req['state']['picked_point_count']
                assert actual['message'] == rule['message_template'].format(n=n, remaining=3-n), c['id']
                assert actual['severity'] == rule['severity'], c['id']
                assert actual['reason_code'] == rule['reason_code'], c['id']
                action = rule['candidate_action'] if rule['candidate_action'] in req['supported_actions'] else None
                assert actual['next_action'] == action, c['id']
            positives += 1
        else:
            error_validator.validate(res)
            assert errors or inv, c['id']
            if 'invariant' in c:
                assert not errors and inv and inv[0] == c['invariant'], (c['id'], inv)
                invariant_coverage.add(inv[0])
                assert res['error']['code'] == 'INCONSISTENT_STATE'
                assert res['error']['details'] == [{'code': 'INCONSISTENT_STATE', 'field': inv[1]}]
            else:
                assert errors and res['error']['code'] == 'INVALID_REQUEST', c['id']
                codes = {'required':'MISSING_FIELD','additionalProperties':'UNKNOWN_FIELD','type':'INVALID_TYPE','anyOf':'INVALID_TYPE','minimum':'OUT_OF_RANGE','maximum':'OUT_OF_RANGE','minLength':'OUT_OF_RANGE','maxLength':'OUT_OF_RANGE','maxItems':'OUT_OF_RANGE','enum':'INVALID_ENUM','const':'INVALID_ENUM','format':'INVALID_FORMAT','pattern':'INVALID_FORMAT','uniqueItems':'DUPLICATE_ITEM'}
                expected_code = res['error']['details'][0]['code']
                assert expected_code in {codes[e.validator] for e in errors}, (c['id'], errors)
            rid = req.get('request_id') if isinstance(req, dict) else None
            expected_rid = rid if isinstance(rid, str) and UUID_PATTERN.fullmatch(rid) else None
            assert res['request_id'] == expected_rid, c['id']
            negatives += 1
    assert coverage == set(rows), ('uncovered rules', set(rows)-coverage)
    assert invariant_coverage == {f'I{i:02}' for i in range(1,10)}
    assert alert_branches == {0,1,2}
    transports = json.loads((FIXTURES / 'transport-cases.json').read_text())
    assert transports['contract_version'] == VERSION
    for c in transports['cases']:
        error_validator.validate(c['expected_response'])
        assert c['expected_status'] in (413,415,422,500)
    sequences = json.loads((FIXTURES / 'qt-sequences.json').read_text())
    assert sequences['contract_version'] == VERSION
    assert all(c['events'] and c['expected'] for c in sequences['cases'])
    # OpenAPI examples must also validate, independently of their source fixtures.
    operation = spec['paths']['/api/v2/agent/guide']['post']
    request_validator.validate(operation['requestBody']['content']['application/json']['example'])
    response_validator.validate(operation['responses']['200']['content']['application/json']['example'])
    print(f'OpenAPI 3.1 valid; YAML/JSON equal; {positives} positive, {negatives} negative HTTP fixtures valid.')
    print(f'All {len(rows)} primary rules, 3 alert branches and I01-I09 covered.')
    print(f'{len(transports["cases"])} transport envelopes valid; {len(sequences["cases"])} Qt sequence specifications present (not executed).')
    print('Design checks only: no Backend endpoint calls, Qt build or UI execution.')


if __name__ == '__main__':
    main()
