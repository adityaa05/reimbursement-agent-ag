import pytest
from endpoints.policyValidator import validate_policy
from models.schemas import PolicyValidationRequest

pytestmark = pytest.mark.integration  # Mark all tests as integration tests


class TestPolicyValidation:
    """Test policy validation with real Confluence data"""

    @pytest.mark.asyncio
    async def test_exceeds_max_amount(self):
        """Verify max amount violation detection"""
        print("\n  [Testing: Exceeds Max Amount]")

        request = PolicyValidationRequest(
            category="Meals",
            amount=75.00,  # Exceeds 50.00 CHF limit
            currency="CHF",
            vendor="Restaurant ABC",
            has_receipt=True,
            invoice_age_days=10,
            company_id="hashgraph_inc",
        )

        result = await validate_policy(request)

        print(
            f"    Result: compliant={result.compliant}, violations={len(result.violations)}"
        )

        assert result.compliant == False
        assert len(result.violations) == 1
        assert result.violations[0].rule == "EXCEEDS_MAX_AMOUNT"
        assert "50.0 CHF" in result.violations[0].message

    @pytest.mark.asyncio
    async def test_missing_receipt(self):
        """Verify receipt requirement enforcement"""
        print("\n  [Testing: Missing Receipt]")

        request = PolicyValidationRequest(
            category="Accommodation",
            amount=200.00,
            currency="CHF",
            has_receipt=False,  # Missing required receipt
            company_id="hashgraph_inc",
        )

        result = await validate_policy(request)

        print(
            f"    Result: compliant={result.compliant}, violations={len(result.violations)}"
        )

        assert result.compliant == False
        assert any(v.rule == "MISSING_RECEIPT" for v in result.violations)

    @pytest.mark.asyncio
    async def test_invoice_too_old(self):
        """Verify max age enforcement"""
        print("\n  [Testing: Invoice Too Old]")

        request = PolicyValidationRequest(
            category="Travel",
            amount=100.00,
            currency="CHF",
            has_receipt=True,
            invoice_age_days=120,  # Exceeds 90 day limit
            company_id="hashgraph_inc",
        )

        result = await validate_policy(request)

        print(
            f"    Result: compliant={result.compliant}, violations={len(result.violations)}"
        )

        assert result.compliant == False
        assert any(v.rule == "INVOICE_TOO_OLD" for v in result.violations)

    @pytest.mark.asyncio
    async def test_compliant_expense(self):
        """Verify compliant expense passes all checks"""
        print("\n  [Testing: Compliant Expense]")

        request = PolicyValidationRequest(
            category="Meals",
            amount=30.00,  # Within 50.00 CHF limit
            currency="CHF",
            vendor="Restaurant ABC",
            has_receipt=True,
            invoice_age_days=10,
            company_id="hashgraph_inc",
        )

        result = await validate_policy(request)

        print(
            f"    Result: compliant={result.compliant}, violations={len(result.violations)}"
        )

        assert result.compliant == True
        assert len(result.violations) == 0
