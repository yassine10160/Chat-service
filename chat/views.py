from django.shortcuts import render


# DEV ONLY: test page for the chat socket
def index(request):
    return render(request, "chat/index.html")
