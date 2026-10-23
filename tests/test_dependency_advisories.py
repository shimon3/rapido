import copy
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.check_dependency_advisories import audit, check_package, fetch_metadata, read_pins


def metadata():
    return {'info': {'name':'Demo', 'version':'1.2.3', 'yanked':False},
            'vulnerabilities': [], 'urls': [{'yanked':False}], 'last_serial':123}


def run(data):
    return audit({'packages':[{'name':'Demo','version':'1.2.3'}]}, {'demo':'1.2.3'}, fetch=lambda url:copy.deepcopy(data))


def test_empty_advisory_list_is_only_a_dated_registry_result():
    result = run(metadata())
    assert result['gate_passed']
    assert result['packages'][0]['source'] == 'https://pypi.org/pypi/demo/1.2.3/json'
    assert result['packages'][0]['last_serial'] == 123
    assert not result['complete_security_review'] and not result['compliance_verified']


def test_active_advisories_block_and_withdrawn_reports_remain_visible():
    data = metadata()
    data['vulnerabilities'] = [{'id':'PYSEC-test','withdrawn':None,'fixed_in':['1.2.4']}]
    result = run(data)
    assert not result['gate_passed']
    assert result['packages'][0]['active_advisory_ids'] == ['PYSEC-test']
    data['vulnerabilities'][0]['withdrawn'] = '2022-06-28T16:39:06Z'
    result = run(data)
    assert result['gate_passed']
    assert result['packages'][0]['advisories'] == data['vulnerabilities']


@pytest.mark.parametrize('withdrawn',[True,{},'', 'tomorrow','2999-01-01T00:00:00Z','2022-01-01T00:00:00'])
def test_malformed_or_future_withdrawal_cannot_hide_an_advisory(withdrawn):
    data = metadata()
    data['vulnerabilities'] = [{'id':'PYSEC-test','withdrawn':withdrawn}]
    assert not run(data)['gate_passed']


@pytest.mark.parametrize('changed',['missing-advisories','wrong-name','wrong-version','invalid-yanked','missing-file-yank','no-files'])
def test_unknown_or_mismatched_registry_fields_do_not_pass(changed):
    data = metadata()
    if changed == 'missing-advisories': del data['vulnerabilities']
    if changed == 'wrong-name': data['info']['name'] = 'other'
    if changed == 'wrong-version': data['info']['version'] = '1.2.4'
    if changed == 'invalid-yanked': data['info']['yanked'] = 'false'
    if changed == 'missing-file-yank': data['urls'] = [{}]
    if changed == 'no-files': data['urls'] = []
    result = run(data)
    assert not result['gate_passed']
    assert result['packages'][0]['status'] == 'unverified'


def test_yanked_releases_or_any_yanked_file_require_review():
    for file_yanked in (False, True):
        data = metadata()
        if file_yanked: data['urls'][0]['yanked'] = True
        else: data['info']['yanked'] = True
        assert not run(data)['gate_passed']


def test_unavailable_registry_and_pin_drift_never_silently_clear():
    def unavailable(url): raise OSError('temporary registry outage')
    inventory = {'packages':[{'name':'Demo','version':'1.2.3'}]}
    result = audit(inventory, {'demo':'1.2.3'}, fetch=unavailable)
    assert not result['gate_passed'] and result['packages'][0]['status'] == 'unverified'
    for pins in ({'demo':'1.2.4'},{'other':'1.0'},{}):
        result = audit(inventory, pins, fetch=lambda url:pytest.fail('Do not query unexpected identities'))
        assert not result['gate_passed'] and result['pin_problems']


def test_constraints_reject_ranges_duplicates_and_empty_files(tmp_path):
    target = tmp_path/'constraints.txt'
    target.write_text('# reviewed\nDemo_pkg==1.2.3\n')
    assert read_pins(target) == {'demo-pkg':'1.2.3'}
    for content in ('', 'demo>=1.0', 'demo==1.*', 'demo==1.0\nDemo==1.0', '--index-url https://example.org'):
        target.write_text(content)
        with pytest.raises(ValueError): read_pins(target)


def test_registry_retry_is_bounded_to_two_attempts():
    with patch('urllib.request.urlopen', side_effect=OSError('outage')) as fetch:
        with pytest.raises(OSError): fetch_metadata('https://pypi.org/pypi/demo/1.2.3/json')
        assert fetch.call_count == 2


def test_reviewed_constraints_cover_the_saved_windows_inventory():
    import json
    root = Path(__file__).resolve().parents[1]
    pins = read_pins(root/'packaging/constraints-windows-build.txt')
    inventory = json.loads((root/'docs/beta-build-inventory-20261023.json').read_text())
    # Exact inventory identity check only, without a live network dependency.
    from scripts.check_dependency_advisories import inventory_packages, pin_problems
    assert pin_problems(inventory_packages(inventory), pins) == []
