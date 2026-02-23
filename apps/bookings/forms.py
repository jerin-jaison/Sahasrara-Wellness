from django import forms
from apps.guests.models import normalize_phone


class GuestInfoForm(forms.Form):
    name = forms.CharField(
        max_length=120,
        label='Full Name',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your full name',
            'autocomplete': 'name',
        }),
    )
    phone = forms.CharField(
        max_length=20,
        label='Mobile Number',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. 98765 43210',
            'autocomplete': 'tel',
            'inputmode': 'numeric',
        }),
    )
    email = forms.EmailField(
        required=False,
        label='Email Address (optional)',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'you@example.com',
            'autocomplete': 'email',
        }),
    )
    notes = forms.CharField(
        required=False,
        max_length=500,
        label='Special Requests (optional)',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Any special requests or health conditions we should know about...',
        }),
    )

    def clean_phone(self):
        raw = self.cleaned_data.get('phone', '')
        try:
            return normalize_phone(raw)
        except ValueError as exc:
            raise forms.ValidationError(
                "Please enter a valid 10-digit Indian mobile number "
                "(e.g. 98765 43210 or +91 98765 43210)."
            ) from exc


class PhoneLookupForm(forms.Form):
    """Used on the session inbox page for phone-based booking lookup."""
    phone = forms.CharField(
        max_length=20,
        label='Mobile Number',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your mobile number to find bookings',
            'inputmode': 'numeric',
        }),
    )

    def clean_phone(self):
        raw = self.cleaned_data.get('phone', '')
        try:
            return normalize_phone(raw)
        except ValueError as exc:
            raise forms.ValidationError(
                "Please enter a valid 10-digit Indian mobile number."
            ) from exc
