from django.shortcuts import render


def index(request):
    """
    Index view for the application.
    """
    return render('index.html', {})
