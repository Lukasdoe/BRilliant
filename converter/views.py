from django.shortcuts import render
from django.views import View
from django.http.response import HttpResponseNotFound, HttpResponse
from urllib.request import urlopen, urlretrieve
from urllib.error import HTTPError, URLError
import re
import json
import os
from bs4 import BeautifulSoup
import openai

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
                    "preview_img": soup.find(attrs={"property": "og:image"}).attrs.get("content")
                }
                return HttpResponse(status=200, content=json.dumps(context))
            except (HTTPError, URLError, ValueError) as e:
                pass
        return HttpResponseNotFound()


class StoryCreateView(View):
    def post(self, request):
        body = json.loads(request.body)
        context = {}
        openai.api_key = os.getenv("OPENAI_API_KEY")

        if body.get("gen_summary"):
            context["summary"] = self.gen_summary(body.get("article_text"))
            if body.get("gen_poll"):
                context["poll"] = self.gen_poll(context["summary"])

        if body.get("gen_quiz"):
            context["quiz"] = self.gen_quiz(body.get("article_text"))

        if body.get("gen_hashtags"):
            context["hashtags"] = self.gen_hashtags(body.get("article_text"))

        preview_path = self.load_preview_picture(body.get("preview_img"))
        return HttpResponse(content=json.dumps(context), status=200, content_type="application/json")

    def gen_summary(self, article_text):
        with open("prompts/summary_prompt.txt", "r") as f:
            prompt_template = f.read().replace("[ARTICLE_TEXT]", article_text)
            return openai.Completion.create(
                engine="davinci",
                prompt=prompt_template,
                max_tokens=188,
                temperature=0.12,
                top_p=0.3,
                frequency_penalty=1,
                presence_penalty=0.1,
                best_of=1,
                stop=["\n\n", "###"],
            ).get("choices")[0].get("text")

    def gen_quiz(self, article_text):
        with open("prompts/quiz_prompt.txt", "r") as f:
            prompt_template = f.read().replace("[ARTICLE_TEXT]", article_text)
            return openai.Completion.create(
                engine="davinci",
                prompt=prompt_template,
                max_tokens=188,
                temperature=0.12,
                top_p=0.3,
                frequency_penalty=1,
                presence_penalty=0.1,
                best_of=1,
                stop=["\n\n", "###"],
            ).get("choices")[0].get("text")

    def gen_hashtags(self, article_text):
        with open("prompts/hashtag_prompt.txt", "r") as f:
            prompt_template = f.read().replace("[ARTICLE_TEXT]", article_text)
            return openai.Completion.create(
                engine="davinci",
                prompt=prompt_template,
                max_tokens=101,
                temperature=0.3,
                top_p=0.7,
                frequency_penalty=0.3,
                presence_penalty=0,
                best_of=1,
                stop=["###"],
            ).get("choices")[0].get("text")

    def gen_poll(self, article_summary):
        with open("prompts/poll_prompt.txt", "r") as f:
            prompt_template = f.read().replace("[SUMMARY]", article_summary)
            return openai.Completion.create(
                engine="davinci",
                prompt=prompt_template,
                max_tokens=64,
                temperature=0.29,
                top_p=0.68,
                frequency_penalty=0,
                presence_penalty=0,
                best_of=1,
                stop=["\n", "####"],
            ).get("choices")[0].get("text")

    def load_preview_picture(self, preview_url):
        if not os.path.isdir("preview_images"):
            os.mkdir("preview_images")
        local_path = os.path.join("preview_images", preview_url.split("/")[-1].split("?")[0])
        urlretrieve(preview_url, local_path)
        return local_path
