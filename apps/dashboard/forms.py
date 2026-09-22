"""Dashboard forms with:
 - ServiceForm: checkbox branch cards + dynamic multi-duration support
"""
from django import forms
from apps.branches.models import Branch, BranchSchedule
from apps.services.models import Service
from apps.workers.models import Worker


_ctrl  = {'class': 'form-control'}
_check = {'class': 'form-check-input'}
_ta    = lambda r: {'class': 'form-control', 'rows': r}

DURATION_CHOICES = Service.DURATION_CHOICES

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
    # Multiple duration choices (30, 45, 60, 90 — all from model)
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

        # Dynamically create price fields for each duration
        for dur_val, dur_label in DURATION_CHOICES:
            field_name = f'price_{dur_val}'
            self.fields[field_name] = forms.DecimalField(
                max_digits=8, decimal_places=2, required=False,
                widget=forms.NumberInput(attrs={
                    **_ctrl, 'min': 0, 'step': '1',
                    'placeholder': f'Price for {dur_val}m'
                }),
                label=f"Price ({dur_val}m)"
            )

        if self.instance and self.instance.pk:
            # Pre-select the current duration
            self.initial['durations'] = [str(self.instance.duration_minutes)]
            
            # Load price for current variant
            current_dur = self.instance.duration_minutes
            self.initial[f'price_{current_dur}'] = self.instance.price
            
            # Look for OTHER variants with the same name to pre-fill their prices
            other_variants = Service.objects.filter(
                name=self.instance.name
            ).exclude(pk=self.instance.pk)
            
            for other_svc in other_variants:
                d = other_svc.duration_minutes
                self.initial[f'price_{d}'] = other_svc.price
                # Also ensure the duration checkbox is checked
                if str(d) not in self.initial['durations']:
                    self.initial['durations'].append(str(d))

    def clean(self):
        cleaned_data = super().clean()
        durations = cleaned_data.get('durations', [])
        
        for dur_str in durations:
            dur_int = int(dur_str)
            field_name = f'price_{dur_int}'
            if not cleaned_data.get(field_name):
                self.add_error(field_name, f'Price for {dur_int} minutes is required.')
            
        return cleaned_data


class WorkerForm(forms.ModelForm):
    class Meta:
        model  = Worker
        fields = ['branch', 'name', 'phone', 'location', 'bio', 'is_active']
        widgets = {
            'branch':      forms.Select(attrs=_ctrl),
            'name':        forms.TextInput(attrs={**_ctrl, 'placeholder': 'Full name'}),
            'location':    forms.TextInput(attrs={**_ctrl, 'placeholder': 'Working location…'}),
            'bio':         forms.Textarea(attrs={**_ta(3), 'placeholder': 'Short therapist bio…'}),
            'phone':       forms.TextInput(attrs={**_ctrl, 'placeholder': '+91 …'}),
            'is_active':   forms.CheckboxInput(attrs=_check),
        }
