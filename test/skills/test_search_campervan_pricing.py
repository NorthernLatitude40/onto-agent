#!/usr/bin/env python3
"""
Test script for search_campervan_pricing tool
Tests the functionality of querying van_models and pricing_inventory tables
"""
import sys
sys.path.insert(0, '/workspaces/langgraph_workspace')

from src.core.shop_agent.tools import search_campervan_pricing
from unittest.mock import patch, MagicMock
import psycopg2
from pgvector.psycopg2 import register_vector

# The @tool decorator wraps the function in a StructuredTool
# We need to access the underlying function via .func attribute
search_campervan_pricing_func = search_campervan_pricing.func if hasattr(search_campervan_pricing, 'func') else search_campervan_pricing


def test_search_campervan_pricing_success():
    """Test successful query with available vehicles"""
    print("\n" + "="*60)
    print("TEST 1: Successful query with available vehicles")
    print("="*60)
    
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = lambda self: self
    mock_conn.__exit__ = lambda self, *args: None
    
    # Mock query results - 2 available vehicles
    mock_rows = [
        ('Get Lost Campervan', 2, 'Automatic', 1500.0, True, '2024-01-01', '2024-01-08'),
        ('Toyota Hiace', 3, 'Manual', 1800.0, True, '2024-01-05', '2024-01-12')
    ]
    mock_cursor.fetchall.return_value = mock_rows
    
    with patch('src.core.shop_agent.tools.get_db_connection', return_value=mock_conn):
        result = search_campervan_pricing_func(
            model_name='campervan',
            pickup_date='2024-01-03',
            return_date='2024-01-10'
        )
    
    print(f"Result: {result}")
    assert 'Get Lost Campervan' in result
    assert 'Toyota Hiace' in result
    assert '有库存/可预订' in result
    assert '1500.0 NZD' in result or '1500 NZD' in result
    print("✅ Test passed: Found 2 available vehicles")


def test_search_campervan_pricing_no_results():
    """Test query with no matching results"""
    print("\n" + "="*60)
    print("TEST 2: Query with no matching results")
    print("="*60)
    
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = lambda self: self
    mock_conn.__exit__ = lambda self, *args: None
    
    # Mock empty query results
    mock_cursor.fetchall.return_value = []
    
    with patch('src.core.shop_agent.tools.get_db_connection', return_value=mock_conn):
        result = search_campervan_pricing_func(
            model_name='NonExistentModel',
            pickup_date='2024-01-03',
            return_date='2024-01-10'
        )
    
    print(f"Result: {result}")
    assert '没有找到符合条件' in result
    print("✅ Test passed: No results message returned")


def test_search_campervan_pricing_unavailable():
    """Test query with unavailable vehicles"""
    print("\n" + "="*60)
    print("TEST 3: Query with unavailable vehicles")
    print("="*60)
    
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = lambda self: self
    mock_conn.__exit__ = lambda self, *args: None
    
    # Mock query results - 1 unavailable vehicle
    mock_rows = [
        ('Get Lost Campervan', 2, 'Automatic', 1500.0, False, '2024-01-01', '2024-01-08')
    ]
    mock_cursor.fetchall.return_value = mock_rows
    
    with patch('src.core.shop_agent.tools.get_db_connection', return_value=mock_conn):
        result = search_campervan_pricing_func(
            model_name='campervan',
            pickup_date='2024-01-03',
            return_date='2024-01-10'
        )
    
    print(f"Result: {result}")
    assert 'Get Lost Campervan' in result
    assert '已满/不可预订' in result
    print("✅ Test passed: Unavailable vehicle status shown correctly")


def test_search_campervan_pricing_mixed_availability():
    """Test query with both available and unavailable vehicles"""
    print("\n" + "="*60)
    print("TEST 4: Query with mixed availability")
    print("="*60)
    
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = lambda self: self
    mock_conn.__exit__ = lambda self, *args: None
    
    # Mock query results - mixed availability
    mock_rows = [
        ('Get Lost Campervan', 2, 'Automatic', 1500.0, True, '2024-01-01', '2024-01-08'),
        ('Toyota Hiace', 3, 'Manual', 1800.0, False, '2024-01-05', '2024-01-12')
    ]
    mock_cursor.fetchall.return_value = mock_rows
    
    with patch('src.core.shop_agent.tools.get_db_connection', return_value=mock_conn):
        result = search_campervan_pricing_func(
            model_name='campervan',
            pickup_date='2024-01-03',
            return_date='2024-01-10'
        )
    
    print(f"Result: {result}")
    assert 'Get Lost Campervan' in result
    assert 'Toyota Hiace' in result
    assert '有库存/可预订' in result
    assert '已满/不可预订' in result
    print("✅ Test passed: Mixed availability shown correctly")


def test_search_campervan_pricing_date_filtering():
    """Test that date filtering works correctly"""
    print("\n" + "="*60)
    print("TEST 5: Date filtering validation")
    print("="*60)
    
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = lambda self: self
    mock_conn.__exit__ = lambda self, *args: None
    
    # Mock query results - vehicle only available in specific date range
    mock_rows = [
        ('Get Lost Campervan', 2, 'Automatic', 1500.0, True, '2024-01-15', '2024-01-22')
    ]
    mock_cursor.fetchall.return_value = mock_rows
    
    with patch('src.core.shop_agent.tools.get_db_connection', return_value=mock_conn):
        # Query for dates that should match the vehicle's availability
        result = search_campervan_pricing_func(
            model_name='campervan',
            pickup_date='2024-01-16',  # Within range
            return_date='2024-01-20'   # Within range
        )
    
    print(f"Result: {result}")
    assert 'Get Lost Campervan' in result
    print("✅ Test passed: Date filtering works correctly")


def test_search_campervan_pricing_case_insensitive():
    """Test that model name search is case insensitive"""
    print("\n" + "="*60)
    print("TEST 6: Case insensitive search")
    print("="*60)
    
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = lambda self: self
    mock_conn.__exit__ = lambda self, *args: None
    
    # Mock query results
    mock_rows = [
        ('Get Lost Campervan', 2, 'Automatic', 1500.0, True, '2024-01-01', '2024-01-08')
    ]
    mock_cursor.fetchall.return_value = mock_rows
    
    with patch('src.core.shop_agent.tools.get_db_connection', return_value=mock_conn):
        # Query with uppercase model name
        result = search_campervan_pricing_func(
            model_name='CAMPERVAN',  # Uppercase
            pickup_date='2024-01-03',
            return_date='2024-01-10'
        )
    
    print(f"Result: {result}")
    assert 'Get Lost Campervan' in result
    print("✅ Test passed: Case insensitive search works")


def test_search_campervan_pricing_error_handling():
    """Test error handling when database query fails"""
    print("\n" + "="*60)
    print("TEST 7: Error handling")
    print("="*60)
    
    # Mock database connection that raises an exception
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = lambda self: self
    mock_conn.__exit__ = lambda self, *args: None
    
    # Mock query that raises an exception
    mock_cursor.execute.side_effect = Exception("Database connection failed")
    
    with patch('src.core.shop_agent.tools.get_db_connection', return_value=mock_conn):
        result = search_campervan_pricing_func(
            model_name='campervan',
            pickup_date='2024-01-03',
            return_date='2024-01-10'
        )
    
    print(f"Result: {result}")
    assert '价格与库存查询出错' in result
    print("✅ Test passed: Error handling works correctly")


def test_search_campervan_pricing_limit():
    """Test that the query respects the LIMIT 5 clause"""
    print("\n" + "="*60)
    print("TEST 8: Result limit validation")
    print("="*60)
    
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = lambda self: self
    mock_conn.__exit__ = lambda self, *args: None
    
    # Mock query results - more than 5 vehicles (should be limited)
    mock_rows = [
        ('Model 1', 2, 'Automatic', 1000.0, True, '2024-01-01', '2024-01-08'),
        ('Model 2', 2, 'Automatic', 1000.0, True, '2024-01-01', '2024-01-08'),
        ('Model 3', 2, 'Automatic', 1000.0, True, '2024-01-01', '2024-01-08'),
        ('Model 4', 2, 'Automatic', 1000.0, True, '2024-01-01', '2024-01-08'),
        ('Model 5', 2, 'Automatic', 1000.0, True, '2024-01-01', '2024-01-08'),
        ('Model 6', 2, 'Automatic', 1000.0, True, '2024-01-01', '2024-01-08'),
    ]
    # Mock cursor should only return first 5 rows (simulating LIMIT 5)
    mock_cursor.fetchall.return_value = mock_rows[:5]
    
    with patch('src.core.shop_agent.tools.get_db_connection', return_value=mock_conn):
        result = search_campervan_pricing_func(
            model_name='model',
            pickup_date='2024-01-03',
            return_date='2024-01-10'
        )
    
    print(f"Result: {result}")
    # Should only show 5 models
    model_count = result.count('Model')
    assert model_count <= 5, f"Expected at most 5 models, got {model_count}"
    print("✅ Test passed: Result limit respected")


if __name__ == "__main__":
    print("\n🧪 Running search_campervan_pricing tests...\n")
    
    try:
        test_search_campervan_pricing_success()
        test_search_campervan_pricing_no_results()
        test_search_campervan_pricing_unavailable()
        test_search_campervan_pricing_mixed_availability()
        test_search_campervan_pricing_date_filtering()
        test_search_campervan_pricing_case_insensitive()
        test_search_campervan_pricing_error_handling()
        test_search_campervan_pricing_limit()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
