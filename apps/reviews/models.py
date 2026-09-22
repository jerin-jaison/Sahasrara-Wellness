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
    def clean_url(self):
        """
        Returns a clean Instagram URL without query parameters or /embed/ suffix.
        Useful for the official blockquote embed script.
        Example: https://www.instagram.com/reels/XYZ/?igsh=... -> https://www.instagram.com/reels/XYZ/
        """
        original_url = self.instagram_url.strip()
        parsed = urlparse(original_url)
        
        # We enforce www.instagram.com to avoid cross-domain redirect issues in frames
        path = parsed.path
        if not path.endswith('/'):
            path += '/'
            
        # Remove any /embed/ if it was manually added by a user
        path = path.replace('/embed/', '/')
            
        return f"https://www.instagram.com{path}"
