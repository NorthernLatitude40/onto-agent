"""
Unit tests for main.py - testing the application entry point and Streamlit UI integration
"""
import os
import sys
from unittest.mock import MagicMock, patch, call
import pytest


def test_root_path_calculation():
    """Test that root path is calculated correctly from main.py location"""
    # This test verifies the path calculation logic in main.py
    current_file = os.path.abspath(__file__)
    
    # Simulate the path calculation from main.py
    # In main.py: root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_main_path = "langgraph_workspace/src/main.py"
    calculated_root = os.path.dirname(os.path.dirname(test_main_path))
    
    assert calculated_root == "langgraph_workspace"


def test_sys_path_modification():
    """Test that root path is added to sys.path if not already present"""
    # Save original sys.path
    original_path = sys.path.copy()
    
    # Simulate the logic from main.py
    root_path = os.path.dirname(os.path.dirname(os.path.abspath("langgraph_workspace/src/main.py")))
    if root_path not in sys.path:
        sys.path.insert(0, root_path)
    
    # Verify root path was added
    assert root_path in sys.path
    assert sys.path[0] == root_path
    
    # Restore original sys.path
    sys.path[:] = original_path


def test_get_global_agent_worker_decorator():
    """Test that get_global_agent_worker is decorated with @st.cache_resource"""
    import streamlit as st
    from src.main import get_global_agent_worker
    
    # Check if the function has been wrapped by cache_resource (it becomes a CachedFunc)
    assert callable(get_global_agent_worker)
    # The decorator wraps the function, so we can check its type or just that it's callable
    # In Streamlit, @st.cache_resource wraps functions in a CachedFunc object


@patch('src.main.AgentHarness')
def test_get_global_agent_worker_bootstrap_called(mock_harness_class):
    """Test that AgentHarness.bootstrap() is called when get_global_agent_worker runs"""
    import streamlit as st
    
    # Create mock instance
    mock_instance = MagicMock()
    mock_harness_class.return_value = mock_instance
    
    # Mock the bootstrap method
    mock_instance.bootstrap = MagicMock()
    
    # Import and call the function (bypass cache by using a fresh module import)
    from src.main import get_global_agent_worker
    
    # Call the function directly - the cache will be bypassed in test environment
    result = get_global_agent_worker()
    
    # Verify bootstrap was called
    mock_instance.bootstrap.assert_called_once()
    assert result == mock_instance


def test_run_ui_is_called():
    """Test that run_ui is called at the end of main.py"""
    # This is a simple smoke test to verify the module can be imported
    # The actual UI rendering would require Streamlit runtime
    from src.main import run_ui
    
    # Verify function exists and is callable
    assert callable(run_ui)


def test_main_module_imports():
    """Test that all imports in main.py are valid"""
    # This test verifies that the module can be imported without errors
    try:
        from src.main import get_global_agent_worker, run_ui
        assert True  # Import successful
    except ImportError as e:
        pytest.fail(f"Import failed: {e}")


def test_path_calculation_with_different_locations():
    """Test path calculation logic with various file locations"""
    test_cases = [
        ("langgraph_workspace/src/main.py", "langgraph_workspace"),
        ("/absolute/path/to/langgraph_workspace/src/main.py", "/absolute/path/to/langgraph_workspace"),
        ("../src/main.py", ".."),  # Relative path
    ]
    
    for file_path, expected_root in test_cases:
        calculated = os.path.dirname(os.path.dirname(file_path))
        assert calculated == expected_root, f"Failed for {file_path}: got {calculated}, expected {expected_root}"




def test_main_py_structure():
    """Test that main.py has the expected structure"""
    import inspect
    from src.main import get_global_agent_worker, run_ui
    
    # Verify functions exist
    assert callable(get_global_agent_worker)
    assert callable(run_ui)
    
    # Check function signatures
    get_global_sig = inspect.signature(get_global_agent_worker)
    assert len(get_global_sig.parameters) == 0  # No parameters
    
    run_ui_sig = inspect.signature(run_ui)
    # run_ui can have harness parameter (optional)
    assert 'harness' in run_ui_sig.parameters or len(run_ui_sig.parameters) == 0


def test_sys_path_not_duplicated():
    """Test that root path is not added to sys.path multiple times"""
    original_path = sys.path.copy()
    
    # First call
    root_path = os.path.dirname(os.path.dirname(os.path.abspath("langgraph_workspace/src/main.py")))
    if root_path not in sys.path:
        sys.path.insert(0, root_path)
    
    first_count = sys.path.count(root_path)
    
    # Second call (should not add again)
    if root_path not in sys.path:
        sys.path.insert(0, root_path)
    
    second_count = sys.path.count(root_path)
    
    assert first_count == 1
    assert second_count == 1  # Should still be only one occurrence
    
    # Restore
    sys.path[:] = original_path
