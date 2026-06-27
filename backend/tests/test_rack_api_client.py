"""Tests for RackApiClient — mock HTTP calls to verify API client behavior."""

import pytest
from unittest.mock import patch, MagicMock
from app.services.rack_api_client import RackApiClient, RackApiError


@pytest.fixture
def client():
    return RackApiClient(
        base_url="http://localhost:8080",
        user_id="test_user",
        client_id="test_client",
        timeout=2.0,
        max_retries=1,
    )


class TestRackApiClient:
    """RackApiClient 单元测试"""

    def test_init(self, client):
        assert client.base_url == "http://localhost:8080"
        assert client.user_id == "test_user"
        assert client.session is not None

    def test_headers_contain_required_fields(self, client):
        headers = client._get_headers()
        assert "userId" in headers
        assert "clientId" in headers
        assert "sessionId" in headers
        assert headers["userId"] == "test_user"
        assert headers["clientId"] == "test_client"

    def test_led_colors_mapping(self):
        assert RackApiClient.LED_COLORS["off"] == 0
        assert RackApiClient.LED_COLORS["red"] == 1
        assert RackApiClient.LED_COLORS["green"] == 2
        assert RackApiClient.LED_COLORS["yellow"] == 3
        assert RackApiClient.LED_COLORS["blue"] == 4
        assert RackApiClient.LED_COLORS["magenta"] == 5
        assert RackApiClient.LED_COLORS["cyan"] == 6
        assert RackApiClient.LED_COLORS["white"] == 7

    def test_indicator_colors_mapping(self):
        assert RackApiClient.INDICATOR_COLORS["off"] == 0
        assert RackApiClient.INDICATOR_COLORS["red"] == 1
        assert RackApiClient.INDICATOR_COLORS["green"] == 4
        assert RackApiClient.INDICATOR_COLORS["all"] == 7

    @patch("app.services.rack_api_client.requests.Session.post")
    def test_light_up_cell_success(self, mock_post, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 0, "message": "OK", "sessionId": "abc"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = client.light_up_cell(
            cell_id="A0010001",
            led_color=2,
            is_blink=False,
            turn_on_time=0,
        )

        assert result["code"] == 0
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "/api/RackCellMgr/LightUpCellLed" in call_args[0][0]
        assert call_args[1]["json"]["cellId"] == "A0010001"
        assert call_args[1]["json"]["ledColor"] == 2

    @patch("app.services.rack_api_client.requests.Session.post")
    def test_light_up_cells_batch_success(self, mock_post, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 0, "message": "OK"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        cells = [
            {"cellId": "A0010001", "ledColor": 2, "blink": False},
            {"cellId": "A0010002", "ledColor": 2, "blink": False},
        ]
        result = client.light_up_cells_batch(cells=cells, voice_text="请取料")

        assert result["code"] == 0
        call_args = mock_post.call_args
        assert call_args[1]["json"]["voiceText"] == "请取料"
        assert len(call_args[1]["json"]["cells"]) == 2

    @patch("app.services.rack_api_client.requests.Session.post")
    def test_api_error_raises_exception(self, mock_post, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 1001, "message": "Invalid cellId"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with pytest.raises(RackApiError, match="API error"):
            client.light_up_cell(cell_id="INVALID", led_color=2)

    @patch("app.services.rack_api_client.requests.Session.post")
    def test_http_error_retries(self, mock_post, client):
        """HTTP 错误后重试，最终抛出异常"""
        from requests.exceptions import HTTPError

        mock_post.side_effect = HTTPError("502 Bad Gateway")

        with pytest.raises(RackApiError, match="Request failed after"):
            client.get_cell_list(rack_id="RACK001")

        assert mock_post.call_count == client.max_retries

    @patch("app.services.rack_api_client.requests.Session.post")
    def test_get_cell_list_with_filters(self, mock_post, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 0,
            "data": [
                {"cellId": "A0010001", "used": False, "electricitys": 3.2},
            ],
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = client.get_cell_list(rack_id="RACK001", page_index=1, page_size=50)

        call_args = mock_post.call_args
        assert call_args[1]["json"]["rackId"] == "RACK001"
        assert call_args[1]["json"]["pageSize"] == 50
        assert len(result["data"]) == 1

    @patch("app.services.rack_api_client.requests.Session.post")
    def test_rack_test(self, mock_post, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 0, "message": "Test started"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = client.rack_test(rack_id="RACK001", test_mode=15, interval=1000)

        call_args = mock_post.call_args
        assert call_args[1]["json"]["testMode"] == 15
        assert result["code"] == 0

    @patch("app.services.rack_api_client.requests.Session.post")
    def test_set_indicator_status(self, mock_post, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 0}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = client.set_indicator_status(
            rack_id="RACK001",
            indicator_id=1,
            indicator_status=1,
            is_blink=True,
        )

        call_args = mock_post.call_args
        assert call_args[1]["json"]["indicatorStatus"] == 1
        assert call_args[1]["json"]["blink"] is True
        assert result["code"] == 0
