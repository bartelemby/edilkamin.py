import json
from io import BytesIO
from unittest import mock

import pytest
from requests.exceptions import HTTPError
from requests.models import Response

from edilkamin import api

token = "token"
mac_address = "aabbccddeeff"


def patch_requests(method, json_response=None, status_code=200):
    response = Response()
    response.status_code = status_code
    response.raw = BytesIO(json.dumps(json_response).encode())
    m_method = mock.Mock(return_value=response)
    return mock.patch(f"edilkamin.api.requests.{method}", m_method)


def patch_requests_get(json_response=None, status_code=200):
    return patch_requests("get", json_response, status_code)


def patch_requests_put(json_response=None, status_code=200):
    return patch_requests("put", json_response, status_code)


def patch_cognito(access_token):
    m_get_user = mock.Mock()
    m_get_user._metadata = {"access_token": access_token}
    m_cognito = mock.Mock()
    m_cognito.return_value.get_user.return_value = m_get_user
    return mock.patch("edilkamin.api.Cognito", m_cognito)


def patch_get_adapters(adapters):
    m_get_adapters = mock.Mock(return_value=adapters)
    return mock.patch("simplepyble.Adapter.get_adapters", m_get_adapters)


def test_sign_in():
    username = "username"
    password = "password"
    access_token = "token"
    m_get_user = mock.Mock()
    m_get_user._metadata = {"access_token": access_token}
    with patch_cognito(access_token) as m_cognito:
        assert api.sign_in(username, password) == access_token
    assert m_cognito().authenticate.call_args_list == [mock.call(password)]
    assert m_cognito().get_user.call_args_list == [mock.call()]


@pytest.mark.parametrize(
    "convert, expected_devices",
    (
        (True, ["a8:03:2a:fe:d5:09"]),
        (False, ["A8:03:2A:FE:D5:0B"]),
    ),
)
def test_discover_devices(convert, expected_devices):
    adapters = [
        mock.Mock(
            scan_get_results=lambda: [
                mock.Mock(
                    identifier=lambda: "EDILKAMIN_EP",
                    address=lambda: "A8:03:2A:FE:D5:0B",
                ),
                mock.Mock(
                    identifier=lambda: "Other device",
                    address=lambda: "00:11:22:33:44:55",
                ),
            ]
        )
    ]
    with patch_get_adapters(adapters):
        assert api.discover_devices(convert) == expected_devices


def test_device_info():
    json_response = {}
    with patch_requests_get(json_response) as m_get:
        assert api.device_info(token, mac_address) == json_response
    assert m_get.call_args_list == [
        mock.call(
            "https://fxtj7xkgc6.execute-api.eu-central-1.amazonaws.com/prod/"
            "device/aabbccddeeff/info",
            headers={"Authorization": "Bearer token"},
        )
    ]


def test_device_info_error():
    """Error status should be raised."""
    json_response = {}
    status_code = 401
    with patch_requests_get(json_response, status_code) as m_get, pytest.raises(
        HTTPError, match="401 Client Error"
    ):
        api.device_info(token, mac_address)
    assert m_get.call_count == 1


def test_mqtt_command():
    json_response = '"Command 0123456789abcdef executed successfully"'
    payload = {"key": "value"}
    with patch_requests_put(json_response) as m_put:
        assert api.mqtt_command(token, mac_address, payload) == json_response
    assert m_put.call_args_list == [
        mock.call(
            "https://fxtj7xkgc6.execute-api.eu-central-1.amazonaws.com/prod/"
            "mqtt/command",
            json={"mac_address": "aabbccddeeff", "key": "value"},
            headers={"Authorization": "Bearer token"},
        )
    ]


def test_mqtt_command_error():
    """Error status should be raised."""
    json_response = {}
    status_code = 401
    payload = {"key": "value"}
    with patch_requests_put(json_response, status_code) as m_put, pytest.raises(
        HTTPError, match="401 Client Error"
    ):
        api.mqtt_command(token, mac_address, payload)
    assert m_put.call_count == 1


@pytest.mark.parametrize(
    "method, expected_value",
    (
        ("set_power_on", 1),
        ("set_power_off", 0),
    ),
)
def test_set_power(method, expected_value):
    json_response = '"Value is already x"'
    set_power_method = getattr(api, method)
    with patch_requests_put(json_response) as m_put:
        assert set_power_method(token, mac_address) == json_response
    assert m_put.call_args_list == [
        mock.call(
            "https://fxtj7xkgc6.execute-api.eu-central-1.amazonaws.com/prod/"
            "mqtt/command",
            json={
                "mac_address": "aabbccddeeff",
                "name": "power",
                "value": expected_value,
            },
            headers={"Authorization": "Bearer token"},
        )
    ]


@pytest.mark.parametrize(
    "power, expected_value",
    (
        (True, api.Power.ON),
        (False, api.Power.OFF),
    ),
)
def test_get_power(power, expected_value):
    json_response = {"status": {"commands": {"power": power}}}
    with patch_requests_get(json_response) as m_get:
        assert api.get_power(token, mac_address) == expected_value
    assert m_get.call_args_list == [
        mock.call(
            "https://fxtj7xkgc6.execute-api.eu-central-1.amazonaws.com/prod/"
            "device/aabbccddeeff/info",
            headers={"Authorization": "Bearer token"},
        )
    ]
