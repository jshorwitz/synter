#!/usr/bin/env python3

"""
Sprint 7 - Production Deployment Test
Tests the production-ready configuration and billing integration.
"""

import requests
import json
import os
import time
from typing import Dict, Any

class ProductionTest:
    def __init__(self):
        # Test against local backend for now, can be changed to production URL
        self.base_url = "http://localhost:8000"
        self.test_results = []
        
    def log_test(self, test_name: str, status: str, details: str = ""):
        """Log test results"""
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.test_results.append(result)
        status_emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_emoji} {test_name}: {status}")
        if details:
            print(f"   Details: {details}")

    def test_health_endpoint(self):
        """Test basic health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    self.log_test("Health Check", "PASS", f"Service healthy: {data}")
                else:
                    self.log_test("Health Check", "FAIL", f"Unexpected health status: {data}")
            else:
                self.log_test("Health Check", "FAIL", f"Status code: {response.status_code}")
        except Exception as e:
            self.log_test("Health Check", "FAIL", str(e))

    def test_billing_endpoints(self):
        """Test billing system endpoints"""
        try:
            # Test workspace endpoint
            response = requests.get(f"{self.base_url}/api/v1/billing/workspace/test-workspace")
            
            if response.status_code in [200, 404]:  # 404 is expected for new workspace
                self.log_test("Billing Workspace Endpoint", "PASS", f"Status: {response.status_code}")
            else:
                self.log_test("Billing Workspace Endpoint", "FAIL", f"Unexpected status: {response.status_code}")
        except Exception as e:
            self.log_test("Billing Workspace Endpoint", "FAIL", str(e))

    def test_report_generation(self):
        """Test report generation with credit consumption"""
        try:
            # Test tracking readiness report (1 credit)
            payload = {
                "url": "https://example.com",
                "workspace_id": "test-workspace"
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/reports/tracking-readiness",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("report_url"):
                    self.log_test("Report Generation", "PASS", f"Generated report: {data.get('report_id')}")
                else:
                    self.log_test("Report Generation", "FAIL", "No report URL in response")
            elif response.status_code == 402:
                # Expected for insufficient credits
                self.log_test("Report Generation", "PASS", "Paywall working (insufficient credits)")
            else:
                self.log_test("Report Generation", "FAIL", f"Status: {response.status_code}")
                
        except Exception as e:
            self.log_test("Report Generation", "FAIL", str(e))

    def test_stripe_integration(self):
        """Test Stripe integration endpoints"""
        try:
            # Test checkout session creation
            payload = {
                "type": "credit_pack",
                "product_id": "credits_10",
                "workspace_id": "test-workspace",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel"
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/billing/create-checkout-session",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("checkout_url"):
                    self.log_test("Stripe Checkout", "PASS", "Checkout session created")
                else:
                    self.log_test("Stripe Checkout", "FAIL", "No checkout URL returned")
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                self.log_test("Stripe Checkout", "FAIL", f"Status: {response.status_code}, Error: {error_data}")
                
        except Exception as e:
            self.log_test("Stripe Checkout", "FAIL", str(e))

    def test_cors_configuration(self):
        """Test CORS headers for production"""
        try:
            response = requests.options(
                f"{self.base_url}/api/v1/reports/tracking-readiness",
                headers={
                    'Origin': 'https://synter.railway.app',
                    'Access-Control-Request-Method': 'POST',
                    'Access-Control-Request-Headers': 'Content-Type'
                }
            )
            
            cors_origins = response.headers.get('Access-Control-Allow-Origin')
            if cors_origins and ('*' in cors_origins or 'railway.app' in cors_origins):
                self.log_test("CORS Configuration", "PASS", f"CORS origins: {cors_origins}")
            else:
                self.log_test("CORS Configuration", "WARN", f"CORS may need adjustment: {cors_origins}")
                
        except Exception as e:
            self.log_test("CORS Configuration", "FAIL", str(e))

    def test_environment_configuration(self):
        """Test environment-specific configurations"""
        try:
            # Check if required environment variables would be accessible
            required_env_vars = [
                'DATABASE_URL',
                'STRIPE_SECRET_KEY',
                'OPENAI_API_KEY'
            ]
            
            missing_vars = []
            for var in required_env_vars:
                if not os.getenv(var):
                    missing_vars.append(var)
            
            if missing_vars:
                self.log_test("Environment Config", "WARN", f"Missing env vars (expected in dev): {missing_vars}")
            else:
                self.log_test("Environment Config", "PASS", "All environment variables present")
                
        except Exception as e:
            self.log_test("Environment Config", "FAIL", str(e))

    def generate_report(self):
        """Generate a comprehensive test report"""
        print("\n" + "="*60)
        print("SPRINT 7 - PRODUCTION DEPLOYMENT TEST REPORT")
        print("="*60)
        
        passed = len([r for r in self.test_results if r["status"] == "PASS"])
        failed = len([r for r in self.test_results if r["status"] == "FAIL"])
        warnings = len([r for r in self.test_results if r["status"] == "WARN"])
        
        print(f"\nTest Summary:")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Warnings: {warnings}")
        print(f"📊 Total: {len(self.test_results)}")
        
        if failed == 0:
            print(f"\n🎉 All critical tests passed! Ready for production deployment.")
        else:
            print(f"\n⚠️  {failed} tests failed. Review issues before production deployment.")
        
        print(f"\nDetailed Results:")
        for result in self.test_results:
            status_emoji = "✅" if result["status"] == "PASS" else "❌" if result["status"] == "FAIL" else "⚠️"
            print(f"{status_emoji} {result['test']}: {result['status']}")
            if result["details"]:
                print(f"   {result['details']}")
        
        # Save results to file
        with open("sprint7_test_results.json", "w") as f:
            json.dump(self.test_results, f, indent=2)
        print(f"\n📄 Detailed results saved to: sprint7_test_results.json")

    def run_all_tests(self):
        """Run all production readiness tests"""
        print("🚀 Starting Sprint 7 Production Deployment Tests...")
        print("="*60)
        
        self.test_health_endpoint()
        self.test_billing_endpoints()
        self.test_report_generation()
        self.test_stripe_integration()
        self.test_cors_configuration()
        self.test_environment_configuration()
        
        self.generate_report()


if __name__ == "__main__":
    tester = ProductionTest()
    tester.run_all_tests()
