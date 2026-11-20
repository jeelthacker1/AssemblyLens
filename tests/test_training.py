import pytest
from backend.training import quality_metrics,parse_cvat
def test_metrics_do_not_hide_uncertainty():
    report=quality_metrics([{'truth_good':True,'predicted_good':True,'latency_ms':10},{'truth_good':False,'predicted_good':True,'latency_ms':20},{'truth_good':True,'predicted_good':None,'latency_ms':30}])
    assert report['precision']==.5 and report['recall']==.5 and report['false_acceptance_rate']==1 and report['uncertain_rate']==1/3
def test_empty_metrics_not_perfect():assert quality_metrics([])['precision'] is None
def test_xml_entities_rejected():
    with pytest.raises(Exception):parse_cvat(b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/passwd">]><annotations>&x;</annotations>')
def test_invalid_boxes_rejected():
    with pytest.raises(ValueError):parse_cvat(b'<annotations><image name="a" width="10" height="10"><box label="x" xtl="0" ytl="0" xbr="20" ybr="5"/></image></annotations>')
