import re
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
        Converts a standard Instagram URL to an embed URL.
        Example: https://www.instagram.com/reels/C_7D_s/ -> https://www.instagram.com/reels/C_7D_s/embed
        """
        url = self.instagram_url.strip()
        if not url.endswith('/'):
            url += '/'
        
        # Ensure it ends with /embed/
        if '/embed/' not in url:
            url += 'embed/'
            
        return url
