from __future__ import annotations

from core.repositories import BaseRepository

from .models import Asset


class AssetRepository(BaseRepository[Asset]):
    model = Asset

    def tag_exists(self, asset_tag: str) -> bool:
        return self.query().filter(asset_tag=asset_tag).exists()
