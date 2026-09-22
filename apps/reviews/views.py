from django.shortcuts import render
from .models import Review

def review_list(request):
    reviews = Review.objects.filter(is_published=True)
    return render(request, 'reviews/review_list.html', {'reviews': reviews})
