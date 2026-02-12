"""
NotesOS - Storage Service
Cloudinary integration for file uploads and management.
"""

import asyncio
import cloudinary
import cloudinary.uploader
import cloudinary.api
from typing import Optional, Union, BinaryIO

from app.config import settings


class StorageService:
    """Handle file uploads to Cloudinary."""

    def __init__(self):
        """Initialize Cloudinary configuration."""
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )

    async def upload_file(
        self, file: Union[bytes, BinaryIO], folder: str, resource_type: str = "auto"
    ) -> dict:
        """
        Upload file to Cloudinary (non-blocking).

        Args:
            file: Raw bytes or file-like object to upload
            folder: Cloudinary folder path
            resource_type: "image", "raw", or "auto"

        Returns:
            dict with url, public_id, format, etc.
        """
        try:
            # Prepare upload options
            upload_options = {
                "folder": folder,
                "resource_type": resource_type,
            }
            if settings.CLOUDINARY_UPLOAD_PRESET:
                upload_options["upload_preset"] = settings.CLOUDINARY_UPLOAD_PRESET

            # Upload to Cloudinary in a thread to avoid blocking the event loop
            result = await asyncio.to_thread(
                cloudinary.uploader.upload, file, **upload_options
            )

            return {
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "format": result.get("format"),
                "size": result.get("bytes"),
                "width": result.get("width"),
                "height": result.get("height"),
            }
        except Exception as e:
            raise Exception(f"File upload failed: {str(e)}")

    async def delete_file(self, public_id: str, resource_type: str = "image") -> bool:
        """
        Delete file from Cloudinary (non-blocking).

        Args:
            public_id: Cloudinary public ID
            resource_type: "image", "raw", etc.

        Returns:
            True if deleted successfully
        """
        try:
            result = await asyncio.to_thread(
                cloudinary.uploader.destroy, public_id, resource_type=resource_type
            )
            return result.get("result") == "ok"
        except Exception as e:
            raise Exception(f"File deletion failed: {str(e)}")

    def get_file_url(
        self, public_id: str, transformations: Optional[dict] = None
    ) -> str:
        """
        Get Cloudinary URL for a file.

        Args:
            public_id: Cloudinary public ID
            transformations: Optional transformations (resize, crop, etc.)

        Returns:
            Full URL to file
        """
        if transformations:
            return cloudinary.CloudinaryImage(public_id).build_url(**transformations)
        return cloudinary.CloudinaryImage(public_id).build_url()


# Singleton instance
storage_service = StorageService()
