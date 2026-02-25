import re
from urllib.parse import urlparse, urljoin
from django.db import models
from apps.core.models import BaseModel

class Review(BaseModel):
    """
    Client reviews featuring Instagram video embeds.
    """
    client_name = models.CharField(max_length=100)
    instagram_url = models.URLField(
        help_text="Paste the Instagram Reel or Post URL (e.g., https://www.instagram.com/reels/XYZ/)"
    )
    is_published = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        ordering = ['sort_order', '-created_at']

    def __str__(self):
        return f"Review from {self.client_name}"

    @property
    def embed_url(self):
        """
        Converts a standard Instagram URL (Post or Reel) to a clean embed URL.
        Strips tracking parameters and ensures /embed/ suffix.
        Example: https://www.instagram.com/reels/XYZ/?igsh=... -> https://www.instagram.com/reels/XYZ/embed/
        """
        original_url = self.instagram_url.strip()
        parsed = urlparse(original_url)
        
        # Reconstruct base path without query params or fragment
        clean_path = parsed.path
        if not clean_path.endswith('/'):
            clean_path += '/'
        
        if '/embed/' not in clean_path:
            clean_path += 'embed/'
            
        return urljoin(f"{parsed.scheme}://{parsed.netloc}", clean_path)
