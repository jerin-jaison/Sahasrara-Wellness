from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from apps.reviews.models import Review
from apps.reviews.forms import ReviewForm
from .decorators import dashboard_admin_required

@dashboard_admin_required
def review_list(request):
    reviews = Review.objects.all().order_by('sort_order', '-created_at')
    return render(request, 'dashboard/reviews/review_list.html', {
        'reviews': reviews,
        'page': 'marketing',
    })

@dashboard_admin_required
def review_create(request):
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Review added successfully.')
            return redirect('dashboard:review_list')
    else:
        form = ReviewForm()
    
    return render(request, 'dashboard/reviews/review_form.html', {
        'form': form,
        'title': 'Add New Review',
        'page': 'marketing',
    })

@dashboard_admin_required
def review_edit(request, pk):
    review = get_object_or_404(Review, pk=pk)
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.save()
            messages.success(request, 'Review updated successfully.')
            return redirect('dashboard:review_list')
    else:
        form = ReviewForm(instance=review)
    
    return render(request, 'dashboard/reviews/review_form.html', {
        'form': form,
        'title': 'Edit Review',
        'review': review,
        'page': 'marketing',
    })

@dashboard_admin_required
def review_delete(request, pk):
    review = get_object_or_404(Review, pk=pk)
    if request.method == 'POST':
        review.delete()
        messages.success(request, 'Review deleted successfully.')
        return redirect('dashboard:review_list')
    return render(request, 'dashboard/reviews/review_confirm_delete.html', {
        'review': review,
        'page': 'marketing',
    })
