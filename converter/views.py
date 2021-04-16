from django.shortcuts import render
from django.views import View
from django.http.response import HttpResponseNotFound, HttpResponse
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
import re
import json
from bs4 import BeautifulSoup


class IndexView(View):
    def get(self, request):
        return render(request, "index.html", context={})


class IndexSearchView(View):
    def get(self, request, search_string):
        if re.match("^https://(www.)?br\\.de/[-a-zA-Z0-9+&@#/%=~_|,]*$", search_string) is not None:
            try:
                urlopen(search_string)
                return HttpResponse(status=200)
            except (HTTPError, URLError, ValueError) as e:
                pass
        return HttpResponseNotFound()


class IndexExtractView(View):
    def get(self, request, extract_string):
        if re.match("^https://(www.)?br\\.de/[-a-zA-Z0-9+&@#/%=~_|,]*$", extract_string) is not None:
            try:
                response_str = urlopen(extract_string).read().decode("utf-8")
                soup = BeautifulSoup(response_str, 'html.parser')
                arts = soup.find(id="articlebody")
                sections = {"Introduction": []}
                last_section_name = "Introduction"
                for item in arts.descendants:
                    if item.name == "p":
                        sections[last_section_name].append(item.text)
                    elif item.name == "h4":
                        last_section_name = item.text
                        sections[item.text] = []
                context = {
                    "headline": soup.find_all("h3")[0].text,
                    "summary": soup.find_all("p")[1].text,
                    "paragraphs": sections,
                }
                return HttpResponse(status=200, content=json.dumps(context))
            except (HTTPError, URLError, ValueError) as e:
                pass
        return HttpResponseNotFound()
