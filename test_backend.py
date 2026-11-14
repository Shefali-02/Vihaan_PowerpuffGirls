"""
Quick Test Script for Munshi Backend
Tests all 7 core endpoints without needing a frontend
"""
import requests
import json
import sys
from pathlib import Path

BASE_URL = "http://localhost:8000"

def print_section(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def test_health():
    """Test 1: Health check"""
    print_section("TEST 1: Health Check")
    try:
        resp = requests.get(f"{BASE_URL}/health")
        resp.raise_for_status()
        data = resp.json()
        print(f"✓ Status: {data['status']}")
        print(f"✓ AI Mode: {data['ai_mode']}")
        if data.get('ai_badge'):
            print(f"⚠️  Badge: {data['ai_badge']}")
        print(f"✓ Documents processed: {data['documents_processed']}")
        print(f"✓ Journals generated: {data['journals_generated']}")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_upload_mock_invoice():
    """Test 2: Upload document (using mock data)"""
    print_section("TEST 2: Upload Document")
    
    # Create a simple mock invoice text file
    invoice_text = """INVOICE
    
From: Tech Supplier Pvt Ltd
GSTIN: 27AABCC1234D1Z5

To: Demo Company Pvt Ltd  
GSTIN: 27AABCD5678E1Z6

Invoice No: INV-2024-001
Date: 2024-01-15

Items:
1. Software License - Rs 10,000

Subtotal: Rs 10,000
CGST @9%: Rs 900
SGST @9%: Rs 900
Total: Rs 11,800
"""
    
    try:
        # Save to temp file
        temp_path = Path("temp_invoice.txt")
        temp_path.write_text(invoice_text)
        
        # Upload
        with open(temp_path, 'rb') as f:
            files = {'file': ('invoice.txt', f, 'text/plain')}
            resp = requests.post(f"{BASE_URL}/documents", files=files)
        
        temp_path.unlink()  # Clean up
        
        resp.raise_for_status()
        data = resp.json()
        
        print(f"✓ Extraction ID: {data['extraction_id']}")
        print(f"✓ Route: {data['route']}")
        print(f"✓ Document Type: {data['document_type']}")
        if data.get('reasons'):
            print(f"  Reasons: {', '.join(data['reasons'])}")
        if data.get('ai_badge'):
            print(f"⚠️  {data['ai_badge']}")
        
        return data['extraction_id'] if data['route'] == 'ready' else None
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return None

def test_draft_journal(extraction_id):
    """Test 3: Generate journal from extraction"""
    print_section("TEST 3: Draft Journal")
    
    if not extraction_id:
        print("⚠️  Skipped - no valid extraction")
        return None
    
    try:
        resp = requests.post(
            f"{BASE_URL}/journals/draft",
            json={"extraction_id": extraction_id}
        )
        resp.raise_for_status()
        data = resp.json()
        
        print(f"✓ Journal ID: {data['journal_id']}")
        print(f"✓ Status: {data['status']}")
        print(f"✓ Review Needed: {data['review_needed']}")
        print(f"✓ Balanced: {data['is_balanced']}")
        print(f"✓ Total Debit: ₹{data['total_debit']/100:,.2f}")
        print(f"✓ Total Credit: ₹{data['total_credit']/100:,.2f}")
        
        journal = data['journal']
        print(f"\nEntries ({len(journal['entries'])}):")
        for entry in journal['entries']:
            dr = f"Dr ₹{entry['debit']/100:,.2f}" if entry['debit'] else ""
            cr = f"Cr ₹{entry['credit']/100:,.2f}" if entry['credit'] else ""
            print(f"  {entry['account']:<25} {dr:>15} {cr:>15}")
        
        return data['journal_id']
        
    except Exception as e:
        print(f"❌ Draft journal failed: {e}")
        return None

def test_post_journal(journal_id):
    """Test 4: Post journal"""
    print_section("TEST 4: Post Journal")
    
    if not journal_id:
        print("⚠️  Skipped - no journal to post")
        return False
    
    try:
        resp = requests.post(f"{BASE_URL}/journals/{journal_id}/post")
        resp.raise_for_status()
        data = resp.json()
        
        print(f"✓ Journal ID: {data['journal_id']}")
        print(f"✓ Status: {data['status']}")
        print(f"✓ Message: {data['message']}")
        return True
        
    except Exception as e:
        print(f"❌ Post journal failed: {e}")
        return False

def test_pnl_report():
    """Test 5: P&L Report"""
    print_section("TEST 5: P&L Report")
    
    try:
        resp = requests.get(f"{BASE_URL}/reports/pnl")
        resp.raise_for_status()
        data = resp.json()
        
        print(f"✓ Period: {data['period']['start']} to {data['period']['end']}")
        print(f"✓ Revenue: ₹{data['revenue']['total_rs']:,.2f}")
        print(f"✓ Expenses: ₹{data['expenses']['total_rs']:,.2f}")
        print(f"✓ Profit: ₹{data['profit']['gross_profit_rs']:,.2f}")
        print(f"✓ Margin: {data['profit']['margin_percent']}%")
        print(f"✓ Journals: {data['meta']['journal_count']}")
        
        if data['revenue']['detail']:
            print("\nRevenue Breakdown:")
            for account, amount in data['revenue']['detail'].items():
                print(f"  {account}: ₹{amount:,.2f}")
        
        if data['expenses']['detail']:
            print("\nExpense Breakdown:")
            for account, amount in data['expenses']['detail'].items():
                print(f"  {account}: ₹{amount:,.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ P&L report failed: {e}")
        return False

def test_gst_summary():
    """Test 6: GST Summary"""
    print_section("TEST 6: GST Summary")
    
    try:
        resp = requests.get(f"{BASE_URL}/reports/gst-summary")
        resp.raise_for_status()
        data = resp.json()
        
        print(f"✓ Period: {data['period']}")
        print(f"✓ Output GST: ₹{data['output_tax']['total_rs']:,.2f}")
        print(f"  - CGST: ₹{data['output_tax']['breakdown']['CGST']:,.2f}")
        print(f"  - SGST: ₹{data['output_tax']['breakdown']['SGST']:,.2f}")
        print(f"  - IGST: ₹{data['output_tax']['breakdown']['IGST']:,.2f}")
        
        print(f"\n✓ Input Tax Credit: ₹{data['input_tax_credit']['total_rs']:,.2f}")
        print(f"  - CGST: ₹{data['input_tax_credit']['breakdown']['CGST']:,.2f}")
        print(f"  - SGST: ₹{data['input_tax_credit']['breakdown']['SGST']:,.2f}")
        print(f"  - IGST: ₹{data['input_tax_credit']['breakdown']['IGST']:,.2f}")
        
        net = data['net_position']['net_rs']
        if net > 0:
            print(f"\n✓ Net GST Payable: ₹{net:,.2f}")
        elif net < 0:
            print(f"\n✓ Net GST Refundable: ₹{-net:,.2f}")
        else:
            print(f"\n✓ Net GST: ₹0.00 (balanced)")
        
        print(f"\n✓ Journals: {data['meta']['journal_count']}")
        if data['meta'].get('mode_badge'):
            print(f"⚠️  Mode: {data['meta']['mode_badge']}")
        
        return True
        
    except Exception as e:
        print(f"❌ GST summary failed: {e}")
        return False

def test_ai_status():
    """Test 7: AI Status"""
    print_section("TEST 7: AI Status")
    
    try:
        resp = requests.get(f"{BASE_URL}/ai/status")
        resp.raise_for_status()
        data = resp.json()
        
        print(f"✓ Mode: {data['mode']}")
        print(f"✓ Backend: {data['backend']}")
        print(f"✓ Mandatory Gateway: {data['mandatory_gateway']}")
        print(f"✓ Provider Fallback: {data['provider_fallback']}")
        if data.get('badge'):
            print(f"⚠️  Badge: {data['badge']}")
        
        return True
        
    except Exception as e:
        print(f"❌ AI status failed: {e}")
        return False

def main():
    print("\n" + "="*70)
    print(" "*20 + "MUNSHI BACKEND TEST SUITE")
    print(" "*25 + "Member 2: AI + Accounting Core")
    print("="*70)
    
    # Check if server is running
    try:
        requests.get(f"{BASE_URL}/health", timeout=2)
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Backend server not running!")
        print("\nStart the server first:")
        print("  python backend/main.py")
        print("\nOr:")
        print("  cd backend")
        print("  uvicorn main:app --reload")
        sys.exit(1)
    
    results = []
    
    # Run all tests
    results.append(("Health Check", test_health()))
    
    extraction_id = test_upload_mock_invoice()
    results.append(("Upload Document", extraction_id is not None))
    
    journal_id = test_draft_journal(extraction_id)
    results.append(("Draft Journal", journal_id is not None))
    
    results.append(("Post Journal", test_post_journal(journal_id)))
    results.append(("P&L Report", test_pnl_report()))
    results.append(("GST Summary", test_gst_summary()))
    results.append(("AI Status", test_ai_status()))
    
    # Summary
    print_section("TEST SUMMARY")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status:>8} - {name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Backend is ready for integration.")
        print("\nNext steps:")
        print("1. Share endpoint URLs with Member 1 (Frontend)")
        print("2. Coordinate with Member 3 (DB + Auth + Trust layer)")
        print("3. Test with real invoices")
        print("4. Practice demo flow")
    else:
        print("\n⚠️  Some tests failed. Check errors above.")
    
    print("="*70 + "\n")
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
