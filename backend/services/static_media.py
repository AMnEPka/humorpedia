"""Static-file behavior for imported media."""
from pathlib import Path

from fastapi.staticfiles import StaticFiles


class MediaStaticFiles(StaticFiles):
    """Serve WebP files with a stable image MIME type across Python images."""

    def file_response(self, full_path, stat_result, scope, status_code=200):
        response = super().file_response(
            full_path,
            stat_result,
            scope,
            status_code=status_code,
        )
        if Path(full_path).suffix.lower() == ".webp":
            response.headers["content-type"] = "image/webp"
        return response