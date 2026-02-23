"""Dashboard forms with:
 - ServiceForm: checkbox branch cards + radio duration (60/90 only)
"""
from django import forms
from apps.branches.models import Branch, BranchSchedule
from apps.services.models import Service
from apps.workers.models import Worker


_ctrl  = {'class': 'form-control'}
_check = {'class': 'form-check-input'}
_ta    = lambda r: {'class': 'form-control', 'rows': r}

DURATION_CHOICES = [(60, '60 minutes'), (90, '90 minutes')]

WEEKDAY_CHOICES = [
    ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'),
    ('3', 'Thursday'), ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday'),
]


class BranchForm(forms.ModelForm):
    class Meta:
        model  = Branch
        fields = [
            'name', 'address', 'city', 'phone', 'email', 'google_maps_url',
            'opening_time', 'closing_time', 'is_active'
        ]
        widgets = {
            'name':            forms.TextInput(attrs={**_ctrl, 'placeholder': 'Branch name'}),
            'address':         forms.Textarea(attrs=_ta(3)),
            'city':            forms.TextInput(attrs={**_ctrl, 'placeholder': 'City'}),
            'phone':           forms.TextInput(attrs={**_ctrl, 'placeholder': '+91 99999 99999'}),
            'email':           forms.EmailInput(attrs=_ctrl),
            'google_maps_url': forms.URLInput(attrs=_ctrl),
            'opening_time':    forms.TimeInput(attrs={**_ctrl, 'type': 'time'}),
            'closing_time':    forms.TimeInput(attrs={**_ctrl, 'type': 'time'}),
            'is_active':       forms.CheckboxInput(attrs=_check),
        }

    working_days = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'checkbox-grid'}),
        required=False,
        initial=['0', '1', '2', '3', '4', '5'],
        help_text="Select working days for this branch."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Load working days from BranchSchedule
            self.initial['working_days'] = [
                str(d) for d in self.instance.get_working_days()
            ]

    def save(self, commit=True):
        branch = super().save(commit=commit)
        if commit:
            self.save_schedules(branch)
        return branch

    def save_schedules(self, branch):
        # Update BranchSchedule records
        selected_days = [int(d) for d in self.cleaned_data.get('working_days', [])]
        
        # We ensure all 7 days exist in the DB, then toggle is_open
        for i in range(7):
            BranchSchedule.objects.update_or_create(
                branch=branch,
                weekday=i,
                defaults={'is_open': i in selected_days}
            )


class ServiceForm(forms.ModelForm):
    # Multiple duration choices (60 or 90)
    durations = forms.MultipleChoiceField(
        choices=DURATION_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'duration-checkbox'}),
        required=True,
        error_messages={'required': 'Please select at least one duration.'},
    )
    # Override branches with checkbox widget
    branches = forms.ModelMultipleChoiceField(
        queryset=Branch.objects.filter(is_active=True).order_by('name'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'branch-checkbox'}),
        required=True,
        error_messages={'required': 'Please select at least one branch.'},
    )

    price_60 = forms.DecimalField(
        max_digits=8, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={**_ctrl, 'min': 0, 'step': '1', 'placeholder': 'Price for 60m'}),
        label="Price (60m)"
    )
    price_90 = forms.DecimalField(
        max_digits=8, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={**_ctrl, 'min': 0, 'step': '1', 'placeholder': 'Price for 90m'}),
        label="Price (90m)"
    )

    class Meta:
        model  = Service
        fields = ['branches', 'name', 'description', 'buffer_minutes', 'is_active']
        widgets = {
            'name':           forms.TextInput(attrs={**_ctrl, 'placeholder': 'e.g. Aromatherapy'}),
            'description':    forms.Textarea(attrs=_ta(3)),
            'buffer_minutes': forms.NumberInput(attrs={**_ctrl, 'min': 0, 'step': 5}),
            'is_active':      forms.CheckboxInput(attrs=_check),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Pre-select the current duration by default
            self.initial['durations'] = [str(self.instance.duration_minutes)]
            
            # Load prices for current and existing variants
            if self.instance.duration_minutes == 60:
                self.initial['price_60'] = self.instance.price
            elif self.instance.duration_minutes == 90:
                self.initial['price_90'] = self.instance.price
            
            # Look for the OTHER variant to pre-fill its price too
            other_duration = 90 if self.instance.duration_minutes == 60 else 60
            other_svc = Service.objects.filter(name=self.instance.name, duration_minutes=other_duration).first()
            if other_svc:
                self.initial[f'price_{other_duration}'] = other_svc.price
                # Also ensure the duration checkbox is checked for the other one
                if str(other_duration) not in self.initial['durations']:
                    self.initial['durations'] = [str(60), str(90)]

    def clean(self):
        cleaned_data = super().clean()
        durations = cleaned_data.get('durations', [])
        
        if '60' in durations and not cleaned_data.get('price_60'):
            self.add_error('price_60', 'Price for 60 minutes is required.')
        if '90' in durations and not cleaned_data.get('price_90'):
            self.add_error('price_90', 'Price for 90 minutes is required.')
            
        return cleaned_data


class WorkerForm(forms.ModelForm):
    class Meta:
        model  = Worker
        fields = ['branch', 'name', 'phone', 'bio', 'is_active']
        widgets = {
            'branch':      forms.Select(attrs=_ctrl),
            'name':        forms.TextInput(attrs={**_ctrl, 'placeholder': 'Full name'}),
            'bio':         forms.Textarea(attrs={**_ta(3), 'placeholder': 'Short therapist bio…'}),
            'phone':       forms.TextInput(attrs={**_ctrl, 'placeholder': '+91 …'}),
            'is_active':   forms.CheckboxInput(attrs=_check),
        }
