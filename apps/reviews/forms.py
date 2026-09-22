from django import forms
from .models import Review

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['client_name', 'instagram_url', 'is_published', 'sort_order']
        widgets = {
            'client_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Client Name'}),
            'instagram_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://www.instagram.com/reels/...'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sort_order': forms.NumberInput(attrs={'class': 'form-control'}),
        }
