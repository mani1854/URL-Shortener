"""schemas package."""

from app.schemas.analytics import (  # noqa: F401
    AnalyticsResponse,
    BrowserDistributionItem,
    CountryDistributionItem,
    DailyClickItem,
    DeviceDistributionItem,
)
from app.schemas.auth import (  # noqa: F401
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.common import APIResponse, ErrorDetail, ErrorResponse, HealthResponse  # noqa: F401
from app.schemas.dashboard import (  # noqa: F401
    PaginatedUserURLsResponse,
    UpdateExpiryRequest,
    UserURLItem,
)
from app.schemas.url import (  # noqa: F401
    URLCreateRequest,
    URLListResponse,
    URLResponse,
    URLStatsResponse,
    URLUpdateRequest,
)
