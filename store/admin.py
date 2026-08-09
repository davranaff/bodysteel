"""BodySteel admin registry.

Feature modules are imported here so Django's autodiscovery keeps one stable
entrypoint while each admin surface stays small and focused.
"""

from store.admin_catalog import (  # noqa: F401
    FilialPhotoAdmin,
    Product360ImageAdmin,
    ProductAdmin,
    ProductImageAdmin,
    ReviewAdmin,
)
from store.admin_commerce import BasketAdmin, CouponAdmin, OrderAdmin  # noqa: F401
from store.admin_content import (  # noqa: F401
    BlogAdmin,
    BrandAdmin,
    CategoryAdmin,
    FilialAdmin,
    MenuAdmin,
    SetOfProductAdmin,
)
from store.admin_shared import (  # noqa: F401
    BasketInline,
    FilialPhotoInline,
    Product360ImageInline,
    ProductImageInline,
    ProductStateFilter,
    StockFilter,
)

# Kept as a compatibility alias for the legacy HTML form test and integrations.
ProductsAdmin = ProductAdmin
