from django.urls import path
from .views import *

app_name = "converter"

urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("converter/input-url/<path:search_string>/", IndexSearchView.as_view(), name="index_search"),
    path("converter/extract-article/<path:extract_string>/", IndexExtractView.as_view(), name="index_search"),
    path("converter/create-story/", StoryCreateView.as_view(), name="story_create"),
]