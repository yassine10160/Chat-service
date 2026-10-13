from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, "chat/index.html")

def room(request, conversation_id):
    return render(request, "chat/room.html", {"conversation_id": conversation_id})
    