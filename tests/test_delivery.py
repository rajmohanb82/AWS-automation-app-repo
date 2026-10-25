"""Controller contract tests; all AWS calls are stubbed, never deployed."""
import runpy
from pathlib import Path
from unittest.mock import Mock
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'deploy.py'

@pytest.mark.parametrize('failure', [None, 'wrong-environment', 'wrong-volume', 'command-failed', 'alb-unhealthy'])
def test_only_verified_release_updates_marker(monkeypatch, failure):
    import boto3
    import time
    env = {'AWS_REGION': 'ap-south-1', 'DEPLOY_ENV': 'dev', 'INSTANCE_ID': 'i-123abc',
           'DATA_VOLUME_ID': 'vol-123abc', 'TARGET_GROUP_ARN': 'test-target',
           'IMAGE': '123456789012.dkr.ecr.ap-south-1.amazonaws.com/autoapp@sha256:' + 'a'*64}
    for k,v in env.items(): monkeypatch.setenv(k,v)
    monkeypatch.chdir(SCRIPT.parents[1])
    monkeypatch.setattr(time, 'sleep', lambda _: None)
    ec2, ssm, elb = Mock(), Mock(), Mock()
    ec2.describe_instances.return_value = {'Reservations': [{'Instances': [{'Tags': [
        {'Key':'Environment','Value':'production' if failure == 'wrong-environment' else 'dev'},
        {'Key':'Project','Value':'autoapp'}]}]}]}
    ec2.describe_volumes.return_value = {'Volumes':[{'Attachments':[{'InstanceId': 'i-other' if failure == 'wrong-volume' else 'i-123abc'}]}]}
    ssm.send_command.return_value = {'Command': {'CommandId':'test-command'}}
    ssm.get_command_invocation.return_value = {'Status': 'Failed' if failure == 'command-failed' else 'Success'}
    # Must be a real exception class for the controller's except clause.
    ssm.exceptions.InvocationDoesNotExist = type('InvocationDoesNotExist', (Exception,), {})
    elb.describe_target_health.return_value = {'TargetHealthDescriptions':[{'TargetHealth':{'State': 'unhealthy' if failure == 'alb-unhealthy' else 'healthy'}}]}
    clients = {'ec2':ec2,'ssm':ssm,'elbv2':elb}
    monkeypatch.setattr(boto3, 'client', lambda name, **kw: clients[name])
    if failure:
        with pytest.raises((AssertionError, SystemExit)):
            runpy.run_path(str(SCRIPT))
        ssm.put_parameter.assert_not_called()
        if failure in {'wrong-environment','wrong-volume'}: ssm.send_command.assert_not_called()
    else:
        runpy.run_path(str(SCRIPT))
        ssm.put_parameter.assert_called_once_with(Name='/autoapp/dev/deployed-digest', Type='String', Value='sha256:'+'a'*64, Overwrite=True)
