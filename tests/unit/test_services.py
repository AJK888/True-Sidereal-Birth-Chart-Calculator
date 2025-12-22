"""
Unit tests for service modules.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services import llm_service, email_service, chart_service
from app.services.llm_service import Gemini3Client


class TestLLMService:
    """Tests for LLM service."""
    
    def test_calculate_gemini3_cost(self):
        """Test cost calculation."""
        result = llm_service.calculate_gemini3_cost(1000, 500)
        assert result['prompt_tokens'] == 1000
        assert result['completion_tokens'] == 500
        assert result['total_tokens'] == 1500
        assert result['input_cost_usd'] > 0
        assert result['output_cost_usd'] > 0
        assert result['total_cost_usd'] > 0
    
    def test_blueprint_to_json(self):
        """Test blueprint JSON conversion."""
        blueprint = {
            "parsed": Mock(model_dump=Mock(return_value={"test": "data"}))
        }
        result = llm_service._blueprint_to_json(blueprint)
        assert "test" in result
        assert "data" in result
    
    def test_sanitize_reading_text(self):
        """Test reading text sanitization."""
        text = "**Bold** *Italic* ```code```"
        result = llm_service.sanitize_reading_text(text)
        assert "**" not in result
        assert "*" not in result or result.count("*") < text.count("*")
    
    @pytest.mark.asyncio
    async def test_gemini_client_stub_mode(self, mock_env_vars):
        """Test Gemini client in stub mode."""
        client = Gemini3Client()
        response = await client.generate(
            system="Test system",
            user="Test user",
            max_output_tokens=100,
            temperature=0.7,
            call_label="test"
        )
        assert "STUB" in response or len(response) > 0
        assert client.call_count == 1


class TestEmailService:
    """Tests for email service."""
    
    def test_send_snapshot_email_no_config(self, monkeypatch):
        """Test snapshot email without SendGrid config."""
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        result = email_service.send_snapshot_email_via_sendgrid(
            "Test snapshot",
            "test@example.com",
            "Test User",
            "2000-01-01",
            "12:00",
            "New York"
        )
        assert result is False
    
    @patch('app.services.email_service.SendGridAPIClient')
    def test_send_snapshot_email_success(self, mock_sg_class, monkeypatch):
        """Test successful snapshot email."""
        monkeypatch.setenv("SENDGRID_API_KEY", "test-key")
        monkeypatch.setenv("SENDGRID_FROM_EMAIL", "test@example.com")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_sg = Mock()
        mock_sg.send.return_value = mock_response
        mock_sg_class.return_value = mock_sg
        
        result = email_service.send_snapshot_email_via_sendgrid(
            "Test snapshot",
            "test@example.com",
            "Test User",
            "2000-01-01",
            "12:00",
            "New York"
        )
        assert result is True


class TestChartService:
    """Tests for chart service."""
    
    def test_generate_chart_hash(self, sample_chart_data):
        """Test chart hash generation."""
        hash1 = chart_service.generate_chart_hash(sample_chart_data, False)
        hash2 = chart_service.generate_chart_hash(sample_chart_data, False)
        assert hash1 == hash2  # Same input should produce same hash
        
        hash3 = chart_service.generate_chart_hash(sample_chart_data, True)
        assert hash1 != hash3  # Different unknown_time should produce different hash
    
    def test_get_full_text_report(self, sample_chart_data):
        """Test full text report generation."""
        report = chart_service.get_full_text_report(sample_chart_data)
        assert "SIDEREAL CHART" in report
        assert "Test User" in report
        assert "Capricorn" in report
    
    def test_get_quick_highlights(self, sample_chart_data):
        """Test quick highlights generation."""
        highlights = chart_service.get_quick_highlights(sample_chart_data, False)
        assert len(highlights) > 0
        assert "Quick Highlights" in highlights or "Capricorn" in highlights
    
    def test_parse_pasted_chart_data(self):
        """Test parsing pasted chart data."""
        pasted_text = """
        === SIDEREAL CHART ===
        Sun: 10°30' Capricorn
        Moon: 20°15' Aries
        === TROPICAL CHART ===
        Sun: 10°30' Capricorn
        """
        result = chart_service.parse_pasted_chart_data(pasted_text)
        assert "chart_data" in result
        assert "planetary_placements" in result



