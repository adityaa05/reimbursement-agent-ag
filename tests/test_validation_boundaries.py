import pytest
from endpoints.OCRValidator import validate_ocr
from models.schemas import SingleOCRValidationRequest, OdooOCRResponse


class TestAmountValidationBoundaries:
    """Test boundary conditions for OCR validation"""

    async def test_perfect_match_returns_match_risk(self):
        """Verify perfect match returns MATCH not LOW"""
        request = SingleOCRValidationRequest(
            odoo_output=OdooOCRResponse(
                invoice_id="test-1", total_amount=85.50, vendor="Test Vendor"
            ),
            employee_claim=85.50,
            invoice_id="INV-001",
            currency="CHF",
        )

        response = await validate_ocr(request)

        assert response.risk_level == "MATCH", "Perfect match must return MATCH"
        assert response.amount_matched == True
        assert response.discrepancy_amount == 0.0

    async def test_boundary_0_01_chf_still_match(self):
        """0.01 CHF difference is within tolerance"""
        request = SingleOCRValidationRequest(
            odoo_output=OdooOCRResponse(
                invoice_id="test-2", total_amount=85.50, vendor="Test"
            ),
            employee_claim=85.51,  # 0.01 difference
            invoice_id="INV-002",
            currency="CHF",
        )

        response = await validate_ocr(request)
        assert response.risk_level == "MATCH"

    async def test_boundary_5_00_chf_low_risk(self):
        """5.00 CHF discrepancy is LOW"""
        request = SingleOCRValidationRequest(
            odoo_output=OdooOCRResponse(
                invoice_id="test-3", total_amount=85.50, vendor="Test"
            ),
            employee_claim=80.50,  # 5.00 difference
            invoice_id="INV-003",
            currency="CHF",
        )

        response = await validate_ocr(request)
        assert response.risk_level == "LOW"
        assert response.discrepancy_amount == 5.00

    async def test_boundary_5_01_chf_medium_risk(self):
        """5.01 CHF discrepancy is MEDIUM"""
        request = SingleOCRValidationRequest(
            odoo_output=OdooOCRResponse(
                invoice_id="test-4", total_amount=85.50, vendor="Test"
            ),
            employee_claim=80.49,  # 5.01 difference
            invoice_id="INV-004",
            currency="CHF",
        )

        response = await validate_ocr(request)
        assert response.risk_level == "MEDIUM"

    async def test_boundary_50_00_chf_medium_risk(self):
        """50.00 CHF discrepancy is MEDIUM"""
        request = SingleOCRValidationRequest(
            odoo_output=OdooOCRResponse(
                invoice_id="test-5", total_amount=100.00, vendor="Test"
            ),
            employee_claim=50.00,  # 50.00 difference
            invoice_id="INV-005",
            currency="CHF",
        )

        response = await validate_ocr(request)
        assert response.risk_level == "MEDIUM"

    async def test_boundary_50_01_chf_high_risk(self):
        """50.01 CHF discrepancy is HIGH"""
        request = SingleOCRValidationRequest(
            odoo_output=OdooOCRResponse(
                invoice_id="test-6", total_amount=100.00, vendor="Test"
            ),
            employee_claim=49.99,  # 50.01 difference
            invoice_id="INV-006",
            currency="CHF",
        )

        response = await validate_ocr(request)
        assert response.risk_level == "HIGH"  # This will fail without Fix #2

    async def test_boundary_100_00_chf_high_risk(self):
        """100.00 CHF discrepancy is HIGH"""
        request = SingleOCRValidationRequest(
            odoo_output=OdooOCRResponse(
                invoice_id="test-7", total_amount=150.00, vendor="Test"
            ),
            employee_claim=50.00,  # 100.00 difference
            invoice_id="INV-007",
            currency="CHF",
        )

        response = await validate_ocr(request)
        assert response.risk_level == "HIGH"

    async def test_boundary_100_01_chf_critical_risk(self):
        """100.01 CHF discrepancy is CRITICAL"""
        request = SingleOCRValidationRequest(
            odoo_output=OdooOCRResponse(
                invoice_id="test-8", total_amount=150.00, vendor="Test"
            ),
            employee_claim=49.99,  # 100.01 difference
            invoice_id="INV-008",
            currency="CHF",
        )

        response = await validate_ocr(request)
        assert response.risk_level == "CRITICAL"

    async def test_ocr_failure_returns_critical(self):
        """Missing total_amount returns CRITICAL"""
        request = SingleOCRValidationRequest(
            odoo_output=OdooOCRResponse(
                invoice_id="test-9", total_amount=None, vendor="Test"  # OCR failed
            ),
            employee_claim=85.50,
            invoice_id="INV-009",
            currency="CHF",
        )

        response = await validate_ocr(request)
        assert response.risk_level == "CRITICAL"
        assert response.verified_amount is None
        assert "manual review required" in response.discrepancy_message.lower()
