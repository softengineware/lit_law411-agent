"""Unit tests for API key utilities."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock

from src.core.api_key_utils import (
    APIKeyManager,
    APIKeyError,
    APIKeyNotFoundError,
    APIKeyExpiredError,
    APIKeyInactiveError,
    APIKeyRateLimitError,
    APIKeyScopeError,
)
from src.models.sqlalchemy.api_key import APIKey
from src.models.sqlalchemy.user import User


class TestAPIKeyManager:
    """Test cases for APIKeyManager."""
    
    def test_generate_api_key(self):
        """Test API key generation."""
        api_key = APIKeyManager.generate_api_key()
        
        assert api_key.startswith("llk_")
        assert len(api_key) > 20
        assert len(api_key) < 50
        
        # Generate multiple keys to ensure they're unique
        keys = [APIKeyManager.generate_api_key() for _ in range(10)]
        assert len(set(keys)) == 10  # All unique
    
    def test_hash_api_key(self):
        """Test API key hashing."""
        api_key = "llk_test_key_123456"
        hash1 = APIKeyManager.hash_api_key(api_key)
        hash2 = APIKeyManager.hash_api_key(api_key)
        
        assert hash1 == hash2  # Same input, same hash
        assert len(hash1) == 64  # SHA256 hex length
        assert hash1 != api_key  # Hash is different from input
        
        # Different keys produce different hashes
        different_key = "llk_different_key_789"
        different_hash = APIKeyManager.hash_api_key(different_key)
        assert hash1 != different_hash
    
    def test_get_key_prefix(self):
        """Test key prefix extraction."""
        api_key = "llk_abcd1234567890"
        prefix = APIKeyManager.get_key_prefix(api_key)
        
        assert prefix == "llk_abcd"
        assert len(prefix) == 8
        
        # Short keys
        short_key = "llk_"
        short_prefix = APIKeyManager.get_key_prefix(short_key)
        assert short_prefix == "llk_"
    
    def test_validate_api_key_format(self):
        """Test API key format validation."""
        # Valid keys
        assert APIKeyManager.validate_api_key_format("llk_abcd1234567890") is True
        assert APIKeyManager.validate_api_key_format("llk_" + "a" * 20) is True
        
        # Invalid keys
        assert APIKeyManager.validate_api_key_format("") is False
        assert APIKeyManager.validate_api_key_format("invalid_key") is False
        assert APIKeyManager.validate_api_key_format("llk_") is False  # Too short
        assert APIKeyManager.validate_api_key_format("llk_" + "a" * 100) is False  # Too long
        assert APIKeyManager.validate_api_key_format("llk_invalid@chars") is False  # Invalid chars
    
    @pytest.mark.asyncio
    async def test_find_api_key_by_hash(self):
        """Test finding API key by hash."""
        # Mock database session
        mock_db = Mock()
        mock_query = Mock()
        mock_filter = Mock()
        mock_first = Mock()
        
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.filter.return_value = mock_first
        
        # Test case: key found
        mock_api_key = Mock(spec=APIKey)
        mock_first.first.return_value = mock_api_key
        
        result = await APIKeyManager.find_api_key_by_hash(mock_db, "test_hash")
        assert result == mock_api_key
        
        # Test case: key not found
        mock_first.first.return_value = None
        result = await APIKeyManager.find_api_key_by_hash(mock_db, "nonexistent_hash")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_find_api_key_by_raw_key(self):
        """Test finding API key by raw key."""
        with patch.object(APIKeyManager, 'hash_api_key') as mock_hash, \
             patch.object(APIKeyManager, 'find_api_key_by_hash') as mock_find:
            
            mock_hash.return_value = "hashed_key"
            mock_api_key = Mock(spec=APIKey)
            mock_find.return_value = mock_api_key
            
            result = await APIKeyManager.find_api_key_by_raw_key(Mock(), "raw_key")
            
            mock_hash.assert_called_once_with("raw_key")
            mock_find.assert_called_once_with(Mock(), "hashed_key")
            assert result == mock_api_key
    
    @pytest.mark.asyncio
    async def test_validate_api_key_success(self):
        """Test successful API key validation."""
        # Create mock objects
        mock_db = Mock()
        mock_api_key = Mock(spec=APIKey)
        mock_user = Mock(spec=User)
        
        # Setup mock API key
        mock_api_key.is_active = True
        mock_api_key.is_expired = False
        mock_api_key.user_id = "user123"
        mock_api_key.has_scope.return_value = True
        mock_api_key.is_rate_limited.return_value = False
        mock_api_key.key_prefix = "llk_test"
        
        # Setup mock user
        mock_user.is_active = True
        
        # Setup mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        with patch.object(APIKeyManager, 'validate_api_key_format', return_value=True), \
             patch.object(APIKeyManager, 'find_api_key_by_raw_key', return_value=mock_api_key):
            
            api_key_obj, user = await APIKeyManager.validate_api_key(
                db=mock_db,
                api_key="llk_test_key",
                required_scope="read",
                check_rate_limit=True
            )
            
            assert api_key_obj == mock_api_key
            assert user == mock_user
    
    @pytest.mark.asyncio
    async def test_validate_api_key_invalid_format(self):
        """Test API key validation with invalid format."""
        with patch.object(APIKeyManager, 'validate_api_key_format', return_value=False):
            with pytest.raises(APIKeyError, match="Invalid API key format"):
                await APIKeyManager.validate_api_key(Mock(), "invalid_key")
    
    @pytest.mark.asyncio
    async def test_validate_api_key_not_found(self):
        """Test API key validation when key not found."""
        with patch.object(APIKeyManager, 'validate_api_key_format', return_value=True), \
             patch.object(APIKeyManager, 'find_api_key_by_raw_key', return_value=None):
            
            with pytest.raises(APIKeyNotFoundError, match="API key not found"):
                await APIKeyManager.validate_api_key(Mock(), "llk_nonexistent")
    
    @pytest.mark.asyncio
    async def test_validate_api_key_inactive(self):
        """Test API key validation with inactive key."""
        mock_api_key = Mock(spec=APIKey)
        mock_api_key.is_active = False
        mock_api_key.key_prefix = "llk_test"
        
        with patch.object(APIKeyManager, 'validate_api_key_format', return_value=True), \
             patch.object(APIKeyManager, 'find_api_key_by_raw_key', return_value=mock_api_key):
            
            with pytest.raises(APIKeyInactiveError, match="API key is inactive"):
                await APIKeyManager.validate_api_key(Mock(), "llk_inactive")
    
    @pytest.mark.asyncio
    async def test_validate_api_key_expired(self):
        """Test API key validation with expired key."""
        mock_api_key = Mock(spec=APIKey)
        mock_api_key.is_active = True
        mock_api_key.is_expired = True
        mock_api_key.key_prefix = "llk_test"
        
        with patch.object(APIKeyManager, 'validate_api_key_format', return_value=True), \
             patch.object(APIKeyManager, 'find_api_key_by_raw_key', return_value=mock_api_key):
            
            with pytest.raises(APIKeyExpiredError, match="API key has expired"):
                await APIKeyManager.validate_api_key(Mock(), "llk_expired")
    
    @pytest.mark.asyncio
    async def test_validate_api_key_insufficient_scope(self):
        """Test API key validation with insufficient scope."""
        mock_api_key = Mock(spec=APIKey)
        mock_user = Mock(spec=User)
        
        mock_api_key.is_active = True
        mock_api_key.is_expired = False
        mock_api_key.user_id = "user123"
        mock_api_key.has_scope.return_value = False  # Missing required scope
        mock_api_key.key_prefix = "llk_test"
        
        mock_user.is_active = True
        
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        with patch.object(APIKeyManager, 'validate_api_key_format', return_value=True), \
             patch.object(APIKeyManager, 'find_api_key_by_raw_key', return_value=mock_api_key):
            
            with pytest.raises(APIKeyScopeError, match="API key missing required scope"):
                await APIKeyManager.validate_api_key(
                    db=mock_db,
                    api_key="llk_limited",
                    required_scope="admin"
                )
    
    @pytest.mark.asyncio
    async def test_validate_api_key_rate_limited(self):
        """Test API key validation with rate limiting."""
        mock_api_key = Mock(spec=APIKey)
        mock_user = Mock(spec=User)
        
        mock_api_key.is_active = True
        mock_api_key.is_expired = False
        mock_api_key.user_id = "user123"
        mock_api_key.has_scope.return_value = True
        mock_api_key.is_rate_limited.side_effect = lambda period: period == "minute"  # Rate limited per minute
        mock_api_key.key_prefix = "llk_test"
        
        mock_user.is_active = True
        
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        with patch.object(APIKeyManager, 'validate_api_key_format', return_value=True), \
             patch.object(APIKeyManager, 'find_api_key_by_raw_key', return_value=mock_api_key):
            
            with pytest.raises(APIKeyRateLimitError, match="Rate limit exceeded: too many requests per minute"):
                await APIKeyManager.validate_api_key(
                    db=mock_db,
                    api_key="llk_limited",
                    check_rate_limit=True
                )
    
    @pytest.mark.asyncio
    async def test_create_api_key(self):
        """Test API key creation."""
        mock_db = Mock()
        mock_user = Mock(spec=User)
        mock_user.id = "user123"
        mock_user.subscription_tier = "premium"
        
        with patch.object(APIKeyManager, 'generate_api_key', return_value="llk_generated"), \
             patch.object(APIKeyManager, 'hash_api_key', return_value="hashed"), \
             patch.object(APIKeyManager, 'get_key_prefix', return_value="llk_gene"):
            
            raw_key, api_key_obj = await APIKeyManager.create_api_key(
                db=mock_db,
                user=mock_user,
                name="Test Key",
                description="Test description",
                scopes=["read", "write"],
                expires_days=30,
                rate_limits={"rate_limit_per_minute": 100},
                metadata={"project": "test"}
            )
            
            assert raw_key == "llk_generated"
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rotate_api_key(self):
        """Test API key rotation."""
        mock_db = Mock()
        mock_api_key = Mock(spec=APIKey)
        
        with patch.object(APIKeyManager, 'generate_api_key', return_value="llk_new"), \
             patch.object(APIKeyManager, 'hash_api_key', return_value="new_hash"), \
             patch.object(APIKeyManager, 'get_key_prefix', return_value="llk_new_"):
            
            new_raw_key, updated_api_key = await APIKeyManager.rotate_api_key(mock_db, mock_api_key)
            
            assert new_raw_key == "llk_new"
            assert updated_api_key == mock_api_key
            assert mock_api_key.key_hash == "new_hash"
            assert mock_api_key.key_prefix == "llk_new_"
            assert mock_api_key.requests_today == 0
            assert mock_api_key.requests_this_hour == 0
            assert mock_api_key.requests_this_minute == 0
            
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_increment_api_key_usage(self):
        """Test API key usage increment."""
        mock_db = Mock()
        mock_api_key = Mock(spec=APIKey)
        mock_api_key.id = "key123"
        mock_api_key.requests_this_minute = 5
        mock_api_key.requests_this_hour = 50
        mock_api_key.requests_today = 500
        
        with patch('src.core.api_key_utils.cache') as mock_cache:
            mock_cache.set = AsyncMock()
            
            await APIKeyManager.increment_api_key_usage(
                db=mock_db,
                api_key_obj=mock_api_key,
                user_agent="Test Agent",
                ip_address="127.0.0.1"
            )
            
            mock_api_key.increment_usage.assert_called_once()
            mock_api_key.update_metadata.assert_called_once_with("Test Agent", "127.0.0.1")
            mock_db.commit.assert_called_once()
            
            # Check cache calls
            assert mock_cache.set.call_count == 3  # minute, hour, day
    
    @pytest.mark.asyncio
    async def test_get_api_key_rate_limit_status(self):
        """Test getting rate limit status."""
        mock_api_key = Mock(spec=APIKey)
        mock_api_key.rate_limit_per_minute = 60
        mock_api_key.rate_limit_per_hour = 1000
        mock_api_key.rate_limit_per_day = 10000
        mock_api_key.requests_this_minute = 10
        mock_api_key.requests_this_hour = 100
        mock_api_key.requests_today = 1000
        mock_api_key.is_rate_limited.return_value = False
        
        status = await APIKeyManager.get_api_key_rate_limit_status(mock_api_key)
        
        assert status["limits"]["per_minute"] == 60
        assert status["current"]["requests_this_minute"] == 10
        assert status["remaining"]["this_minute"] == 50
        assert "reset_times" in status
        assert "is_rate_limited" in status


class TestAPIKeyModel:
    """Test cases for APIKey model methods."""
    
    def test_generate_key(self):
        """Test API key generation method."""
        key = APIKey.generate_key()
        assert key.startswith("llk_")
        assert len(key) > 20
    
    def test_hash_key(self):
        """Test API key hashing method."""
        key = "llk_test_key"
        hash1 = APIKey.hash_key(key)
        hash2 = APIKey.hash_key(key)
        assert hash1 == hash2
        assert len(hash1) == 64
    
    def test_get_key_prefix(self):
        """Test key prefix extraction method."""
        key = "llk_abcd1234"
        prefix = APIKey.get_key_prefix(key)
        assert prefix == "llk_abcd"
    
    def test_is_expired(self):
        """Test expiration check."""
        # Non-expiring key
        api_key = APIKey()
        api_key.expires_at = None
        assert api_key.is_expired is False
        
        # Expired key
        api_key.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert api_key.is_expired is True
        
        # Future expiration
        api_key.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        assert api_key.is_expired is False
    
    def test_is_valid(self):
        """Test validity check."""
        api_key = APIKey()
        api_key.is_active = True
        api_key.expires_at = None
        assert api_key.is_valid is True
        
        # Inactive key
        api_key.is_active = False
        assert api_key.is_valid is False
        
        # Expired key
        api_key.is_active = True
        api_key.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert api_key.is_valid is False
    
    def test_is_rate_limited(self):
        """Test rate limiting check."""
        api_key = APIKey()
        api_key.rate_limit_per_minute = 10
        api_key.rate_limit_per_hour = 100
        api_key.rate_limit_per_day = 1000
        
        # Not rate limited
        api_key.requests_this_minute = 5
        api_key.requests_this_hour = 50
        api_key.requests_today = 500
        
        assert api_key.is_rate_limited("minute") is False
        assert api_key.is_rate_limited("hour") is False
        assert api_key.is_rate_limited("day") is False
        
        # Rate limited per minute
        api_key.requests_this_minute = 15
        assert api_key.is_rate_limited("minute") is True
    
    def test_has_scope(self):
        """Test scope checking."""
        api_key = APIKey()
        
        # No scopes
        api_key.scopes = None
        assert api_key.has_scope("read") is False
        
        # Empty scopes
        api_key.scopes = []
        assert api_key.has_scope("read") is False
        
        # Has specific scope
        api_key.scopes = ["read", "write"]
        assert api_key.has_scope("read") is True
        assert api_key.has_scope("admin") is False
        
        # Wildcard scope
        api_key.scopes = ["*"]
        assert api_key.has_scope("anything") is True
    
    def test_increment_usage(self):
        """Test usage increment."""
        api_key = APIKey()
        api_key.total_requests = 0
        api_key.requests_today = 0
        api_key.requests_this_hour = 0
        api_key.requests_this_minute = 0
        
        api_key.increment_usage()
        
        assert api_key.total_requests == 1
        assert api_key.requests_today == 1
        assert api_key.requests_this_hour == 1
        assert api_key.requests_this_minute == 1
        assert api_key.last_used_at is not None
    
    def test_reset_usage_counters(self):
        """Test usage counter resets."""
        api_key = APIKey()
        api_key.requests_today = 10
        api_key.requests_this_hour = 5
        api_key.requests_this_minute = 2
        
        api_key.reset_daily_usage()
        assert api_key.requests_today == 0
        
        api_key.reset_hourly_usage()
        assert api_key.requests_this_hour == 0
        
        api_key.reset_minute_usage()
        assert api_key.requests_this_minute == 0
    
    def test_update_metadata(self):
        """Test metadata update."""
        api_key = APIKey()
        
        api_key.update_metadata(user_agent="Test Agent", ip="127.0.0.1")
        
        assert api_key.user_agent == "Test Agent"
        assert api_key.last_used_ip == "127.0.0.1"
    
    def test_to_safe_dict(self):
        """Test safe dictionary conversion."""
        api_key = APIKey()
        api_key.id = "test123"
        api_key.name = "Test Key"
        api_key.key_hash = "secret_hash"
        api_key.is_active = True
        api_key.expires_at = None
        
        safe_dict = api_key.to_safe_dict()
        
        assert "key_hash" not in safe_dict
        assert safe_dict["name"] == "Test Key"
        assert safe_dict["is_expired"] is False
        assert safe_dict["is_valid"] is True