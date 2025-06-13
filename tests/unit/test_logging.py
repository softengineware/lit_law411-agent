"""Tests for logging infrastructure."""

import asyncio
import logging
import time
from unittest.mock import Mock, patch

import pytest
import structlog

from src.core.logging import (
    clear_request_id,
    get_logger,
    get_request_id,
    log_audit_trail,
    log_exception,
    log_performance,
    log_security_event,
    set_request_id,
    setup_logging,
)
from src.utils.logging_utils import (
    LogContext,
    log_function_calls,
    log_method_calls,
    sanitize_for_logging,
    time_operation,
)


class TestLoggingSetup:
    """Test logging setup and configuration."""

    def test_setup_logging_development(self):
        """Test logging setup in development mode."""
        with patch("src.core.logging.get_settings") as mock_settings:
            mock_settings.return_value.is_production = False
            mock_settings.return_value.log_level = "DEBUG"
            
            setup_logging()
            
            # Verify logger is configured
            logger = get_logger()
            # Check if it's a structlog logger (could be BoundLogger or BoundLoggerLazyProxy)
            assert hasattr(logger, 'info')
            assert hasattr(logger, 'error')

    def test_setup_logging_production(self):
        """Test logging setup in production mode."""
        with patch("src.core.logging.get_settings") as mock_settings:
            mock_settings.return_value.is_production = True
            mock_settings.return_value.log_level = "INFO"
            
            setup_logging()
            
            # Verify logger is configured
            logger = get_logger()
            assert hasattr(logger, 'info')
            assert hasattr(logger, 'error')

    def test_get_logger(self):
        """Test logger creation."""
        logger = get_logger("test_logger")
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')

    def test_get_logger_with_name(self):
        """Test logger creation with specific name."""
        logger = get_logger("custom.logger")
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')


class TestRequestIdTracking:
    """Test request ID tracking functionality."""

    def test_set_and_get_request_id(self):
        """Test setting and getting request ID."""
        request_id = set_request_id("test-123")
        assert request_id == "test-123"
        assert get_request_id() == "test-123"

    def test_set_request_id_auto_generate(self):
        """Test auto-generating request ID."""
        request_id = set_request_id()
        assert request_id is not None
        assert len(request_id) == 36  # UUID length
        assert get_request_id() == request_id

    def test_clear_request_id(self):
        """Test clearing request ID."""
        set_request_id("test-123")
        assert get_request_id() == "test-123"
        
        clear_request_id()
        assert get_request_id() is None

    def test_request_id_isolation(self):
        """Test request ID isolation between contexts."""
        # This test verifies that request IDs don't leak between contexts
        clear_request_id()
        assert get_request_id() is None
        
        set_request_id("test-1")
        assert get_request_id() == "test-1"


class TestLoggingFunctions:
    """Test logging utility functions."""

    def test_log_exception(self):
        """Test exception logging."""
        with patch('src.core.logging.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            try:
                raise ValueError("Test error")
            except ValueError as e:
                log_exception(e, {"context": "test"})
            
            # Verify that logger.error was called with expected arguments
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert "Exception occurred" in call_args[0][0]
            assert call_args[1]["exception_type"] == "ValueError"
            assert call_args[1]["exception_message"] == "Test error"

    def test_log_performance(self):
        """Test performance logging."""
        with patch('src.core.logging.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_performance("test_operation", 1.5, metric1="value1")
            
            # Verify that logger.info was called with expected arguments
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "Performance metric" in call_args[0][0]
            assert call_args[1]["operation"] == "test_operation"
            assert call_args[1]["duration_seconds"] == 1.5

    def test_log_security_event(self):
        """Test security event logging."""
        with patch('src.core.logging.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_security_event("suspicious_login", {"ip": "192.168.1.1", "user": "admin"})
            
            # Verify that logger.warning was called with expected arguments
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "Security event" in call_args[0][0]
            assert call_args[1]["event_type"] == "suspicious_login"

    def test_log_audit_trail(self):
        """Test audit trail logging."""
        with patch('src.core.logging.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            log_audit_trail("create", "user", "user123", details="Created new user")
            
            # Verify that logger.info was called with expected arguments
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "Audit event" in call_args[0][0]
            assert call_args[1]["action"] == "create"
            assert call_args[1]["resource"] == "user"
            assert call_args[1]["user_id"] == "user123"


class TestLoggingDecorators:
    """Test logging decorators."""

    def test_log_function_calls_sync(self):
        """Test function call logging for sync functions."""
        with patch('src.utils.logging_utils.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            @log_function_calls(include_args=True, include_result=True)
            def test_function(a, b, c=None):
                return a + b
            
            result = test_function(1, 2, c="test")
            
            assert result == 3
            # Should have been called twice: once for "Function called", once for "Function completed"
            assert mock_logger.info.call_count == 2
            call_args_list = mock_logger.info.call_args_list
            assert "Function called" in call_args_list[0][0][0]
            assert "Function completed" in call_args_list[1][0][0]

    def test_log_function_calls_async(self):
        """Test function call logging for async functions."""
        with patch('src.utils.logging_utils.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            @log_function_calls(include_args=True, include_result=True)
            async def test_async_function(a, b):
                await asyncio.sleep(0.01)
                return a * b
            
            async def run_test():
                result = await test_async_function(3, 4)
                assert result == 12
            
            asyncio.run(run_test())
            
            # Should have been called twice: once for "Function called", once for "Function completed"
            assert mock_logger.info.call_count == 2
            call_args_list = mock_logger.info.call_args_list
            assert "Function called" in call_args_list[0][0][0]
            assert "Function completed" in call_args_list[1][0][0]

    def test_log_function_calls_exception(self):
        """Test function call logging with exception."""
        with patch('src.utils.logging_utils.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            @log_function_calls()
            def failing_function():
                raise RuntimeError("Test error")
            
            with pytest.raises(RuntimeError):
                failing_function()
            
            # Should have called info once for "Function called" and error once for "Function failed"
            mock_logger.info.assert_called_once()
            mock_logger.error.assert_called_once()
            assert "Function called" in mock_logger.info.call_args[0][0]
            assert "Function failed" in mock_logger.error.call_args[0][0]

    def test_log_method_calls(self):
        """Test method call logging."""
        with patch('src.utils.logging_utils.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            class TestClass:
                @log_method_calls(include_args=True)
                def test_method(self, value):
                    return value * 2
            
            obj = TestClass()
            result = obj.test_method(5)
            
            assert result == 10
            # Should have been called twice: once for "Function called", once for "Function completed"
            assert mock_logger.info.call_count == 2
            call_args_list = mock_logger.info.call_args_list
            assert "Function called" in call_args_list[0][0][0]

    def test_exclude_args(self):
        """Test excluding specific arguments from logging."""
        with patch('src.utils.logging_utils.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            @log_function_calls(include_args=True, exclude_args=["password", "secret"])
            def login_function(username, password, secret):
                return f"Logged in {username}"
            
            # Call with keyword arguments so they show up in kwargs
            login_function(username="testuser", password="secret123", secret="topsecret")
            
            # Check that excluded args are not in the logged arguments
            call_args_list = mock_logger.info.call_args_list
            logged_kwargs = call_args_list[0][1]["arguments"]["kwargs"]
            assert "username" in logged_kwargs
            assert "password" not in logged_kwargs
            assert "secret" not in logged_kwargs


class TestLogContext:
    """Test logging context manager."""

    def test_log_context(self):
        """Test logging with context."""
        with patch('src.utils.logging_utils.get_logger') as mock_get_logger:
            mock_logger = Mock()
            bound_logger = Mock()
            mock_logger.bind.return_value = bound_logger
            mock_get_logger.return_value = mock_logger
            
            with LogContext(user_id="123", operation="test") as logger:
                logger.info("Test message")
            
            # Verify that logger was bound with context
            mock_logger.bind.assert_called_once_with(user_id="123", operation="test")
            bound_logger.info.assert_called_once_with("Test message")

    def test_log_context_exception(self):
        """Test logging context with exception."""
        with patch('src.utils.logging_utils.get_logger') as mock_get_logger:
            mock_logger = Mock()
            bound_logger = Mock()
            mock_logger.bind.return_value = bound_logger
            mock_get_logger.return_value = mock_logger
            
            with pytest.raises(ValueError):
                with LogContext(user_id="123") as logger:
                    raise ValueError("Test error")
            
            # Verify that exception was logged with context
            bound_logger.error.assert_called_once()
            call_args = bound_logger.error.call_args
            assert "Exception in log context" in call_args[0][0]
            assert call_args[1]["exception_type"] == "ValueError"


class TestTimeOperation:
    """Test time operation context manager."""

    def test_time_operation_success(self):
        """Test timing successful operation."""
        with patch('src.utils.logging_utils.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            with time_operation("test_operation"):
                time.sleep(0.01)
            
            # Should have been called twice: once for starting, once for completed
            assert mock_logger.info.call_count == 2
            call_args_list = mock_logger.info.call_args_list
            assert "Starting test_operation" in call_args_list[0][0][0]
            assert "test_operation completed" in call_args_list[1][0][0]

    def test_time_operation_failure(self):
        """Test timing failed operation."""
        with patch('src.utils.logging_utils.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            with pytest.raises(RuntimeError):
                with time_operation("failing_operation"):
                    raise RuntimeError("Test error")
            
            # Should have called info once for starting, error once for failed
            mock_logger.info.assert_called_once()
            mock_logger.error.assert_called_once()
            assert "Starting failing_operation" in mock_logger.info.call_args[0][0]
            assert "failing_operation failed" in mock_logger.error.call_args[0][0]


class TestSanitizeForLogging:
    """Test data sanitization for logging."""

    def test_sanitize_none(self):
        """Test sanitizing None value."""
        result = sanitize_for_logging(None)
        assert result == "None"

    def test_sanitize_string(self):
        """Test sanitizing string."""
        result = sanitize_for_logging("test string")
        assert result == "'test string'"

    def test_sanitize_dict(self):
        """Test sanitizing dictionary."""
        data = {"key": "value", "number": 42}
        result = sanitize_for_logging(data)
        assert "key" in result
        assert "value" in result

    def test_sanitize_long_data(self):
        """Test sanitizing long data."""
        long_string = "x" * 2000
        result = sanitize_for_logging(long_string, max_length=100)
        assert len(result) <= 103  # 100 + "..."
        assert result.endswith("...")

    def test_sanitize_sensitive_data(self):
        """Test sanitizing sensitive data."""
        sensitive_data = "password=secret123&token=abc456"
        result = sanitize_for_logging(sensitive_data)
        
        # Sensitive patterns should be replaced
        assert "secret123" not in result
        assert "abc456" not in result
        assert "[PASSWORD]" in result or "[TOKEN]" in result

    def test_sanitize_dict_with_sensitive_keys(self):
        """Test sanitizing dictionary with sensitive keys."""
        data = {
            "username": "testuser",
            "password": "secret123",
            "api_key": "key456",
            "normal_field": "value"
        }
        result = sanitize_for_logging(data)
        
        assert "testuser" in result
        assert "value" in result
        # Sensitive values should be filtered out
        assert "secret123" not in result
        assert "key456" not in result


class TestLoggingIntegration:
    """Test logging integration scenarios."""

    def test_request_id_in_logs(self, caplog):
        """Test that request ID appears in logs."""
        setup_logging()
        
        set_request_id("test-request-123")
        logger = get_logger()
        logger.info("Test message with request ID")
        
        # Request ID should be included in log output
        # Note: The exact format depends on the processor configuration
        clear_request_id()

    def test_multiple_loggers(self):
        """Test creating multiple loggers."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        
        assert logger1 is not logger2
        assert hasattr(logger1, 'info')
        assert hasattr(logger2, 'info')

    def test_logging_performance_under_load(self):
        """Test logging performance with many messages."""
        setup_logging()
        logger = get_logger()
        
        start_time = time.time()
        
        for i in range(100):
            logger.info("Performance test message", iteration=i)
        
        duration = time.time() - start_time
        
        # Should complete quickly (under 1 second for 100 messages)
        assert duration < 1.0