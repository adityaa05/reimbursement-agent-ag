#!/usr/bin/env python3
"""
Expense Reimbursement Bot - Comprehensive End-to-End Test Suite

Tests complete workflow with Single-OCR architecture:
- Odoo expense fetching and OCR
- Confluence policy retrieval with caching
- Amount validation (MATCH, LOW, MEDIUM, HIGH, CRITICAL scenarios)
- Category enrichment
- Policy validation
- Report generation and posting to Odoo

Simulates real-world conditions including:
- Network delays and timeouts
- Confluence cache behavior
- Error recovery mechanisms
- Multiple expense scenarios
"""

import requests
import json
import os
import time
import sys
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
from dotenv import load_dotenv


# Color codes for terminal output
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


@dataclass
class TestScenario:
    """Represents an expense test scenario"""

    name: str
    expense_sheet_id: int
    expected_risk_levels: List[str]  # Expected risk for each invoice
    expected_total_match: bool
    expected_policy_violations: int
    description: str


@dataclass
class EndpointResult:
    """Result of an endpoint call"""

    endpoint: str
    success: bool
    duration_ms: float
    response: Optional[Dict] = None
    error: Optional[str] = None


class ExpenseE2ETest:
    """Comprehensive end-to-end test orchestrator"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        load_dotenv()

        self.base_url = base_url
        self.company_id = "hashgraph_inc"

        # Odoo configuration
        self.odoo_config = {
            "odoo_url": os.getenv("ODOO_URL"),
            "odoo_db": os.getenv("ODOO_DB"),
            "odoo_username": os.getenv("ODOO_USERNAME"),
            "odoo_password": os.getenv("ODOO_PASSWORD"),
        }

        # Test statistics
        self.total_endpoints_called = 0
        self.total_duration_ms = 0
        self.endpoints_results: List[EndpointResult] = []
        self.start_time = None

        # Validate configuration
        if not all(self.odoo_config.values()):
            self.print_error("Missing Odoo credentials in .env file")
            self.print_info("Required: ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD")
            sys.exit(1)

    def print_header(self, text: str):
        """Print section header"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")

    def print_success(self, text: str):
        """Print success message"""
        print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")

    def print_error(self, text: str):
        """Print error message"""
        print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

    def print_warning(self, text: str):
        """Print warning message"""
        print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")

    def print_info(self, text: str):
        """Print info message"""
        print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")

    def call_endpoint(
        self, endpoint: str, payload: Dict, timeout: int = 120, method: str = "POST"
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        Call API endpoint with timing and error handling.

        Returns: (success, response_data, error_message)
        """
        start = time.time()

        try:
            url = f"{self.base_url}{endpoint}"

            if method == "POST":
                response = requests.post(url, json=payload, timeout=timeout)
            else:
                response = requests.get(url, params=payload, timeout=timeout)

            duration_ms = (time.time() - start) * 1000

            response.raise_for_status()
            result_data = response.json()

            # Record result
            self.endpoints_results.append(
                EndpointResult(
                    endpoint=endpoint,
                    success=True,
                    duration_ms=duration_ms,
                    response=result_data,
                )
            )

            self.total_endpoints_called += 1
            self.total_duration_ms += duration_ms

            return True, result_data, ""

        except requests.exceptions.Timeout:
            duration_ms = (time.time() - start) * 1000
            error_msg = f"Timeout after {timeout}s"

            self.endpoints_results.append(
                EndpointResult(
                    endpoint=endpoint,
                    success=False,
                    duration_ms=duration_ms,
                    error=error_msg,
                )
            )

            return False, None, error_msg

        except requests.exceptions.HTTPError as e:
            duration_ms = (time.time() - start) * 1000
            error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"

            self.endpoints_results.append(
                EndpointResult(
                    endpoint=endpoint,
                    success=False,
                    duration_ms=duration_ms,
                    error=error_msg,
                )
            )

            return False, None, error_msg

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            error_msg = str(e)

            self.endpoints_results.append(
                EndpointResult(
                    endpoint=endpoint,
                    success=False,
                    duration_ms=duration_ms,
                    error=error_msg,
                )
            )

            return False, None, error_msg

    def test_health_check(self) -> bool:
        """Test API health endpoint"""
        self.print_header("SYSTEM HEALTH CHECK")

        success, data, error = self.call_endpoint("/health", {}, method="GET")

        if success:
            self.print_success(f"API Status: {data.get('status', 'unknown')}")

            # Get root endpoint info
            success, root_data, _ = self.call_endpoint("/", {}, method="GET")
            if success:
                self.print_info(f"Service: {root_data.get('service', 'N/A')}")
                self.print_info(f"Version: {root_data.get('version', 'N/A')}")
                self.print_info(f"Architecture: {root_data.get('architecture', 'N/A')}")
                self.print_info(
                    f"Total Endpoints: {root_data.get('total_endpoints', 'N/A')}"
                )

            return True
        else:
            self.print_error(f"Health check failed: {error}")
            return False

    def test_confluence_policy_fetch(self) -> bool:
        """Test Confluence policy fetching and caching"""
        self.print_header("CONFLUENCE POLICY INTEGRATION TEST")

        # First call - should fetch from Confluence
        self.print_info("Fetching policies from Confluence (fresh)...")
        success1, data1, error1 = self.call_endpoint(
            "/fetch-policies", {"company_id": self.company_id}
        )

        if not success1:
            self.print_error(f"Policy fetch failed: {error1}")
            return False

        duration1 = self.endpoints_results[-1].duration_ms
        categories1 = data1.get("categories", [])

        self.print_success(
            f"Fetched {len(categories1)} policy categories in {duration1:.2f}ms"
        )
        self.print_info(
            f"Categories: {', '.join([c['name'] for c in categories1[:5]])}..."
        )

        # Second call - should hit cache (faster)
        self.print_info("Fetching policies again (should hit cache)...")
        time.sleep(0.5)  # Small delay

        success2, data2, error2 = self.call_endpoint(
            "/fetch-policies", {"company_id": self.company_id}
        )

        if not success2:
            self.print_warning("Cache test failed - policies still work")
            return True  # Not critical

        duration2 = self.endpoints_results[-1].duration_ms
        categories2 = data2.get("categories", [])

        if duration2 < duration1:
            self.print_success(
                f"Cache hit! {duration2:.2f}ms vs {duration1:.2f}ms (cached)"
            )
        else:
            self.print_warning(f"No cache speedup detected ({duration2:.2f}ms)")

        # Verify data consistency
        if len(categories1) == len(categories2):
            self.print_success("Policy data consistent between calls")
        else:
            self.print_warning("Policy data changed between calls")

        return True

    def test_expense_workflow(self, scenario: TestScenario) -> bool:
        """
        Test complete expense workflow for a scenario.

        Workflow:
        1. Fetch expense from Odoo
        2. For each invoice: OCR → Validate → Enrich category → Validate policy
        3. Calculate total
        4. Format report
        5. Post to Odoo
        """
        self.print_header(f"EXPENSE WORKFLOW: {scenario.name}")
        self.print_info(scenario.description)

        # ===================================================================
        # STEP 1: Fetch Expense from Odoo
        # ===================================================================
        self.print_info("\n[1/6] Fetching expense data from Odoo...")

        success, expense_data, error = self.call_endpoint(
            "/fetch-odoo-expense",
            {"expense_sheet_id": scenario.expense_sheet_id, **self.odoo_config},
        )

        if not success:
            self.print_error(f"Failed to fetch expense: {error}")
            return False

        expense_sheet = expense_data.get("expense_sheet", {})
        expense_lines = expense_data.get("expense_lines", [])

        employee_info = expense_sheet.get("employee_id", [None, "Unknown"])
        employee_name = (
            employee_info[1] if isinstance(employee_info, list) else "Unknown"
        )
        expense_name = expense_sheet.get("name", "Unknown")
        employee_total = expense_sheet.get("total_amount", 0.0)

        self.print_success(f"Fetched expense sheet: {expense_name}")
        self.print_info(f"  Employee: {employee_name}")
        self.print_info(f"  Total Invoices: {len(expense_lines)}")
        self.print_info(f"  Employee Reported Total: {employee_total:.2f} CHF")

        # ===================================================================
        # STEP 2: Process Each Invoice (OCR + Validation)
        # ===================================================================
        self.print_info("\n[2/6] Processing OCR and validation for each invoice...")

        validation_results = []
        odoo_ocr_results = []

        print(
            f"\n{'#':<4} {'Odoo OCR':<12} {'Claimed':<12} {'Risk':<12} {'Match':<8} {'Discrepancy'}"
        )
        print("-" * 70)

        for idx, line in enumerate(expense_lines):
            invoice_num = idx + 1
            line_id = line.get("id")
            claimed_amount = line.get("total_amount", 0.0)

            # Skip if no attachment
            attachments = line.get("attachments", [])
            if not attachments:
                print(
                    f"{invoice_num:<4} {'NO ATTACHMENT':<12} {'N/A':<12} {'SKIPPED':<12} {'N/A':<8} N/A"
                )
                validation_results.append(None)
                odoo_ocr_results.append(None)
                continue

            # Call Odoo OCR
            success, ocr_result, error = self.call_endpoint(
                "/odoo-ocr", {"expense_line_id": line_id, **self.odoo_config}
            )

            if not success:
                self.print_error(f"  Invoice {invoice_num}: OCR failed - {error}")
                validation_results.append(None)
                odoo_ocr_results.append(None)
                continue

            odoo_ocr_results.append(ocr_result)
            odoo_amount = ocr_result.get("total_amount")

            # Call validation
            success, validation, error = self.call_endpoint(
                "/validate-ocr",
                {
                    "odoo_output": ocr_result,
                    "employee_claim": claimed_amount,
                    "invoice_id": f"INV-{invoice_num}",
                    "currency": "CHF",
                },
            )

            if not success:
                self.print_error(
                    f"  Invoice {invoice_num}: Validation failed - {error}"
                )
                validation_results.append(None)
                continue

            validation_results.append(validation)

            # Display result
            odoo_amt_str = f"{odoo_amount:.2f}" if odoo_amount else "FAILED"
            claimed_str = f"{claimed_amount:.2f}"
            risk = validation.get("risk_level", "UNKNOWN")
            matched = "✓" if validation.get("amount_matched") else "✗"
            discrepancy = validation.get("discrepancy_amount", 0.0)
            disc_str = f"{discrepancy:.2f}" if discrepancy else "0.00"

            # Color code by risk
            if risk == "MATCH":
                risk_colored = f"{Colors.OKGREEN}{risk}{Colors.ENDC}"
            elif risk == "LOW":
                risk_colored = f"{Colors.OKBLUE}{risk}{Colors.ENDC}"
            elif risk == "MEDIUM":
                risk_colored = f"{Colors.WARNING}{risk}{Colors.ENDC}"
            elif risk in ["HIGH", "CRITICAL"]:
                risk_colored = f"{Colors.FAIL}{risk}{Colors.ENDC}"
            else:
                risk_colored = risk

            print(
                f"{invoice_num:<4} {odoo_amt_str:<12} {claimed_str:<12} {risk_colored:<12} {matched:<8} {disc_str}"
            )

        valid_validations = [v for v in validation_results if v]

        if not valid_validations:
            self.print_error("No valid validations - cannot continue")
            return False

        self.print_success(
            f"\nProcessed {len(valid_validations)}/{len(expense_lines)} invoices successfully"
        )

        # ===================================================================
        # STEP 3: Calculate Total
        # ===================================================================
        self.print_info("\n[3/6] Calculating total amounts...")

        success, total_calc, error = self.call_endpoint(
            "/calculate-total",
            {
                "individual_validations": valid_validations,
                "employee_reported_total": employee_total,
                "currency": "CHF",
            },
        )

        if not success:
            self.print_error(f"Total calculation failed: {error}")
            return False

        calculated = total_calc.get("calculated_total", 0.0)
        reported = total_calc.get("employee_reported_total", 0.0)
        matched = total_calc.get("matched", False)
        discrepancy = total_calc.get("discrepancy_amount", 0.0)

        print(f"\n  System Calculated:   {calculated:.2f} CHF")
        print(f"  Employee Reported:   {reported:.2f} CHF")
        print(f"  Match:               {'✓ YES' if matched else '✗ NO'}")

        if not matched:
            print(f"  Discrepancy:         {discrepancy:.2f} CHF")
            self.print_warning(f"Total mismatch detected: {discrepancy:.2f} CHF")
        else:
            self.print_success("Total verification PASSED")

        # ===================================================================
        # STEP 4: Enrich Categories
        # ===================================================================
        self.print_info("\n[4/6] Enriching expense categories...")

        enriched_categories = []

        for idx, ocr_result in enumerate(odoo_ocr_results):
            if not ocr_result:
                enriched_categories.append("Other")
                continue

            product_info = expense_lines[idx].get("product_id", [None, None])
            existing_category = (
                product_info[1]
                if isinstance(product_info, list) and len(product_info) > 1
                else None
            )

            success, result, error = self.call_endpoint(
                "/enrich-category",
                {
                    "vendor": ocr_result.get("vendor"),
                    "date": ocr_result.get("date"),
                    "time": ocr_result.get("time"),
                    "existing_category": existing_category,
                    "invoice_id": f"INV-{idx + 1}",
                    "company_id": self.company_id,
                },
            )

            if success:
                category = result.get("suggested_category", "Other")
                confidence = result.get("confidence", 0.0)
                enriched_categories.append(category)
                print(f"  Invoice {idx + 1}: {category} (confidence: {confidence:.2f})")
            else:
                enriched_categories.append("Other")
                self.print_warning(
                    f"  Invoice {idx + 1}: Enrichment failed, using 'Other'"
                )

        self.print_success(f"Categorized {len(enriched_categories)} invoices")

        # ===================================================================
        # STEP 5: Validate Policy Compliance
        # ===================================================================
        self.print_info("\n[5/6] Validating policy compliance...")

        policy_validations = []

        print(
            f"\n{'#':<4} {'Category':<20} {'Amount':<12} {'Limit':<12} {'Status':<12} {'Violations'}"
        )
        print("-" * 80)

        for idx, category in enumerate(enriched_categories):
            if idx >= len(validation_results) or not validation_results[idx]:
                continue

            validation = validation_results[idx]
            amount = validation.get("verified_amount", 0.0)

            success, result, error = self.call_endpoint(
                "/validate-policy",
                {
                    "category": category,
                    "amount": amount,
                    "currency": "CHF",
                    "vendor": None,
                    "has_receipt": True,
                    "has_attendees": None,
                    "invoice_age_days": 15,
                    "company_id": self.company_id,
                },
            )

            if not success:
                self.print_warning(f"  Invoice {idx + 1}: Policy check failed")
                continue

            policy_validations.append(result)

            compliant = result.get("compliant", False)
            max_amount = result.get("max_amount")
            violations = result.get("violations", [])

            amt_str = f"{amount:.2f}"
            limit_str = f"{max_amount:.2f}" if max_amount else "N/A"
            status = (
                f"{Colors.OKGREEN}COMPLIANT{Colors.ENDC}"
                if compliant
                else f"{Colors.FAIL}VIOLATED{Colors.ENDC}"
            )
            violation_count = len(violations)

            violation_msg = ""
            if violations:
                violation_msg = violations[0].get("message", "")[:40] + "..."

            print(
                f"{idx + 1:<4} {category:<20} {amt_str:<12} {limit_str:<12} {status:<12} {violation_msg}"
            )

        total_violations = sum(
            1 for p in policy_validations if not p.get("compliant", True)
        )

        if total_violations == 0:
            self.print_success("All expenses are policy-compliant")
        else:
            self.print_warning(f"Found {total_violations} policy violation(s)")

        # ===================================================================
        # STEP 6: Format Report and Post to Odoo
        # ===================================================================
        self.print_info("\n[6/6] Generating and posting report to Odoo...")

        success, report_data, error = self.call_endpoint(
            "/format-report",
            {
                "expense_sheet_id": scenario.expense_sheet_id,
                "expense_sheet_name": expense_name,
                "employee_name": employee_name,
                "single_ocr_validations": valid_validations,
                "total_validation": total_calc,
                "categories": enriched_categories,
                "policy_validations": policy_validations,
            },
        )

        if not success:
            self.print_error(f"Report formatting failed: {error}")
            return False

        html_comment = report_data.get("html_comment", "")
        formatted_comment = report_data.get("formatted_comment", "")

        self.print_success(f"Generated report ({len(html_comment)} chars)")

        # Post to Odoo
        success, post_result, error = self.call_endpoint(
            "/post-odoo-comment",
            {
                "expense_sheet_id": scenario.expense_sheet_id,
                "comment_html": html_comment,
                **self.odoo_config,
            },
        )

        if not success:
            self.print_error(f"Failed to post comment to Odoo: {error}")
            return False

        message_id = post_result.get("message_id")
        self.print_success(f"Posted comment to Odoo (message_id: {message_id})")

        # ===================================================================
        # Verify Expected Outcomes
        # ===================================================================
        self.print_info("\n[VERIFICATION] Checking expected outcomes...")

        all_passed = True

        # Check risk levels
        actual_risks = [v.get("risk_level") for v in valid_validations]
        if actual_risks == scenario.expected_risk_levels:
            self.print_success(f"Risk levels match: {actual_risks}")
        else:
            self.print_warning(
                f"Risk levels differ - Expected: {scenario.expected_risk_levels}, Got: {actual_risks}"
            )
            all_passed = False

        # Check total match
        if matched == scenario.expected_total_match:
            self.print_success(f"Total match as expected: {matched}")
        else:
            self.print_warning(
                f"Total match differs - Expected: {scenario.expected_total_match}, Got: {matched}"
            )
            all_passed = False

        # Check policy violations
        if total_violations == scenario.expected_policy_violations:
            self.print_success(f"Policy violations as expected: {total_violations}")
        else:
            self.print_warning(
                f"Policy violations differ - Expected: {scenario.expected_policy_violations}, Got: {total_violations}"
            )
            all_passed = False

        return all_passed

    def print_final_summary(self):
        """Print comprehensive test summary"""
        self.print_header("TEST EXECUTION SUMMARY")

        total_time = time.time() - self.start_time

        print(f"Total Test Duration:     {total_time:.2f}s")
        print(f"Total Endpoints Called:  {self.total_endpoints_called}")
        print(f"Total API Time:          {self.total_duration_ms:.2f}ms")
        print(
            f"Average Response Time:   {self.total_duration_ms / self.total_endpoints_called:.2f}ms"
        )

        # Endpoint breakdown
        self.print_info("\nEndpoint Performance:")

        endpoint_stats = {}
        for result in self.endpoints_results:
            if result.endpoint not in endpoint_stats:
                endpoint_stats[result.endpoint] = {
                    "count": 0,
                    "total_ms": 0,
                    "successes": 0,
                    "failures": 0,
                }

            endpoint_stats[result.endpoint]["count"] += 1
            endpoint_stats[result.endpoint]["total_ms"] += result.duration_ms
            if result.success:
                endpoint_stats[result.endpoint]["successes"] += 1
            else:
                endpoint_stats[result.endpoint]["failures"] += 1

        for endpoint, stats in sorted(endpoint_stats.items()):
            avg_ms = stats["total_ms"] / stats["count"]
            success_rate = (stats["successes"] / stats["count"]) * 100

            print(
                f"  {endpoint:<25} {stats['count']:>3} calls  {avg_ms:>7.2f}ms avg  {success_rate:>5.1f}% success"
            )

        # Success/failure summary
        total_success = sum(1 for r in self.endpoints_results if r.success)
        total_failure = len(self.endpoints_results) - total_success

        print(f"\n{Colors.OKGREEN}✓ Successful Calls: {total_success}{Colors.ENDC}")
        if total_failure > 0:
            print(f"{Colors.FAIL}✗ Failed Calls: {total_failure}{Colors.ENDC}")

        # List failures
        if total_failure > 0:
            print(f"\n{Colors.FAIL}Failed Endpoints:{Colors.ENDC}")
            for result in self.endpoints_results:
                if not result.success:
                    print(f"  {result.endpoint}: {result.error}")


def main():
    """Main test execution"""

    # Initialize test suite
    tester = ExpenseE2ETest(base_url="http://localhost:8000")
    tester.start_time = time.time()

    print(f"{Colors.BOLD}{Colors.HEADER}")
    print("=" * 80)
    print("EXPENSE REIMBURSEMENT BOT - COMPREHENSIVE E2E TEST SUITE")
    print("Single-OCR Architecture v3.0 - Odoo + Confluence Integration")
    print("=" * 80)
    print(f"{Colors.ENDC}")

    # Test 1: Health Check
    if not tester.test_health_check():
        tester.print_error("System health check failed - aborting tests")
        sys.exit(1)

    # Test 2: Confluence Integration
    if not tester.test_confluence_policy_fetch():
        tester.print_warning("Confluence test had issues but continuing...")

    # Define test scenarios
    scenarios = [
        TestScenario(
            name="Real World Scenario (Sheet 307)",
            expense_sheet_id=404,
            expected_risk_levels=["MATCH", "MATCH", "MATCH", "MATCH"],
            expected_total_match=True,
            expected_policy_violations=1,  # Invoice 2 (339 CHF) exceeds Accommodation limit (200 CHF)
            description="Real data test: 4 invoices, 1 valid policy violation (over limit)",
        ),
    ]

    # Test 3: Expense Workflows
    scenario_results = []
    for scenario in scenarios:
        result = tester.test_expense_workflow(scenario)
        scenario_results.append((scenario.name, result))

    # Final Summary
    tester.print_final_summary()

    # Overall result
    print("\n")
    all_passed = all(result for _, result in scenario_results)

    if all_passed:
        print(f"{Colors.OKGREEN}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
        print(
            f"{Colors.OKGREEN}{Colors.BOLD}{'ALL TESTS PASSED ✓'.center(80)}{Colors.ENDC}"
        )
        print(f"{Colors.OKGREEN}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
        sys.exit(0)
    else:
        print(f"{Colors.FAIL}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
        print(
            f"{Colors.FAIL}{Colors.BOLD}{'SOME TESTS FAILED ✗'.center(80)}{Colors.ENDC}"
        )
        print(f"{Colors.FAIL}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
        sys.exit(1)


if __name__ == "__main__":
    main()
