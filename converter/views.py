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
from converter.utils import tokenize


from PIL import Image, ImageFont, ImageDraw
from pytrends.request import TrendReq
BLUE = (86, 135, 204, 255)
WHITE = (255, 255, 255, 255)

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
                del sections[last_section_name][-1]
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


class TokenNumberView(View):
    def post(self, request):
        article_text = json.loads(request.body).get("article_text")
        blank = len(list(tokenize(article_text)))
        context = {
            "summary": blank + len(list(tokenize(open("prompts/summary_prompt.txt").read()))) + 188,
            "quiz": blank + len(list(tokenize(open("prompts/quiz_prompt.txt").read()))) + 188,
            "poll": 150 + len(list(tokenize(open("prompts/poll_prompt.txt").read()))) + 64,
            "hashtags": blank + len(list(tokenize(open("prompts/hashtag_prompt.txt").read()))) + 101,
        }
        return HttpResponse(content=json.dumps(context))


class StoryCreateView(View):
    def post(self, request):
        body = json.loads(request.body)
        context = {}
        openai.api_key = os.getenv("OPENAI_API_KEY")

        summary = self.gen_summary(body.get("article_text"))
        context["summary"] = summary.replace("2. ", "").replace("3. ", "")
        if body.get("gen_poll"):
            context["poll"] = self.gen_poll(context["summary"])
            poll = context["poll"]
        else:
            poll = ""

        if body.get("gen_quiz"):
            context["quiz"], quiz_answers = self.gen_quiz(body.get("article_text"))
            quiz = context["quiz"]
        else:
            quiz = ""
            quiz_answers = ""

        if body.get("gen_hashtags"):
            context["hashtags"] = self.gen_hashtags(context["summary"])
            print(context["hashtags"])
            hashtags = context["hashtags"].split(",")
            try:
                if len(hashtags) > 2:
                    hashtags = [h.strip() for h in hashtags]
                    pytrends = TrendReq(hl='de-DE', tz=120)
                    kw_list = hashtags[:5]
                    print(kw_list)
                    pytrends.build_payload(kw_list, cat=0, timeframe='today 1-m')
                    interest = pytrends.interest_by_region(resolution='COUNTRY', inc_low_vol=True, inc_geo_code=False)
                    print(interest)
                    print(interest[interest.index == "Deutschland"])
                    interest_dict = interest[interest.index == "Deutschland"].to_dict('records')[0]
                    hashtags = sorted(interest_dict, key=interest_dict.get, reverse=True)

                hashtags = ['#' + "".join(e for e in h if e.isalnum() and e != '-').lower() for h in hashtags]
            except:
                hashtags = ['#' + "".join(e for e in h if e.isalnum() and e != '-').lower() for h in hashtags]
        else:
            hashtags = list()

        print(hashtags)
        context["hashtags"] = hashtags
        hashtags = hashtags[:2]
        preview_path = self.load_preview_picture(body.get("preview_img"))

        self.gen_stories(preview_path, summary, hashtags, quiz.split("1.")[0], quiz_answers, poll,
                         body.get("gen_quiz"), body.get("gen_hashtags"), body.get("gen_poll"))

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
            quiz_question = openai.Completion.create(
                engine="davinci",
                prompt=prompt_template,
                max_tokens=64,
                temperature=0.12,
                top_p=0.3,
                frequency_penalty=1,
                presence_penalty=0.1,
                best_of=1,
                stop=["\n\n", "###", "2."],
            ).get("choices")[0].get("text").replace("1. ", "")
        with open("prompts/quiz_answers_prompt.txt", "r") as f:
            prompt_template = f.read().replace("[ARTICLE_TEXT]", article_text).replace("[QUESTION]", quiz_question)
            quiz_answers = openai.Completion.create(
                engine="davinci",
                prompt=prompt_template,
                max_tokens=150,
                temperature=0.12,
                top_p=0.3,
                frequency_penalty=1,
                presence_penalty=0.1,
                best_of=1,
                stop=["\n\n", "4."],
            ).get("choices")[0].get("text")
        return quiz_question + "\n\n1." + quiz_answers, quiz_answers.replace("2.", "").replace("3.", "").splitlines()

    def gen_hashtags(self, article_summary):
        with open("prompts/hashtag_prompt.txt", "r") as f:
            prompt_template = f.read().replace("[SUMMARY]", article_summary)
            print(prompt_template)
            return openai.Completion.create(
                engine="davinci",
                prompt=prompt_template,
                max_tokens=101,
                temperature=0.3,
                top_p=1,
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

    def gen_stories(self, image_path, summary, hashtags, quiz_question, quiz_answers,poll, gen_quiz, gen_hashtags, gen_poll,
                    text_color=WHITE, text_background=BLUE, font='fonts/Roboto-Bold.ttf',
                    font_size=40, location="centered"):

        image = Image.open(image_path)
        image_size = image.size

        # crop to 16 by 9
        size_16_9 = ((image_size[1]//16)*9, image_size[1])
        #print("16, 9", size_16_9)
        image1 = image.crop((0, 0, size_16_9[0], size_16_9[1]))
        #print("Image1", image1.size)
        image2 = image.crop((image_size[0]//2 - size_16_9[0]//2, 0, image_size[0]//2 + size_16_9[0]//2, size_16_9[1]))
        image3 = image.crop((image_size[0] - size_16_9[0], 0, image_size[0], size_16_9[1]))

        if summary.count("2. ") and summary.count("3. "):
            sentences = [
                summary.split("2. ")[0],
                summary.split("2. ")[1].split("3. ")[0],
                summary.split("2. ")[1].split("3. ")[1],
            ]
        else:
            sentences = summary.replace("2. ", "").replace("3. ", "").split(".")

        image_with_text_1 = self.text_on_image(image1, " ".join(sentences[:2]), font, font_size,
                                               text_color, text_background, location)
        if gen_hashtags:
            second_story = sentences[2] + " " + hashtags[0]
        else:
            second_story = sentences[2]
        image_with_text_2 = self.text_on_image(image2, second_story, font, font_size,
                                               text_color, text_background, location)

        if gen_poll:
            poll = self.process_poll("poll_template/poll.png", poll, font)
            image_with_text_2 = self.embed_poll(poll, image_with_text_2, "")

        if gen_quiz:
            quiz = self.process_quiz("quiz_templates/quiz" + str(len(quiz_answers)) + ".png",
                                     quiz_question, quiz_answers, font, font)

            image_with_quiz = self.embed_quiz(quiz, image3, location)
        # TODO: add story

        image_with_text_1.save("static/story1.png")
        image_with_text_2.save("static/story2.png")
        if gen_quiz:
            image_with_quiz.save("static/story3.png")


    def wrap_text(self, text, width, font):
        text_lines = []
        text_line = []
        text = text.replace('\n', ' [br] ')
        words = text.split()

        for word in words:
            if word == '[br]':
                text_lines.append(' '.join(text_line))
                text_line = []
                continue
            text_line.append(word)
            w, h = font.getsize(' '.join(text_line))
            if w > width:
                text_line.pop()
                text_lines.append(' '.join(text_line))
                text_line = [word]

        if len(text_line) > 0:
            text_lines.append(' '.join(text_line))

        return text_lines

    def text_on_image(self, image, text, font,
                      font_size, text_color, text_background, location):
        image_size = image.size

        title_font = ImageFont.truetype(font, font_size)
        editable = ImageDraw.Draw(image)

        margin = 40
        text = self.wrap_text(text, image_size[0] - margin * 2, title_font)

        whole_text_size = editable.textsize("\n".join(text), font=title_font)

        if location == "centered":
            y = image_size[1] // 2 - whole_text_size[1] // 2
        else:
            y = location

        relative = 0
        for line in text:
            text_size = editable.textsize(line, font=title_font)
            margin = (image_size[0] - text_size[0]) // 2

            editable.rectangle((margin - 3, y + relative, margin + text_size[0] + 3, y + text_size[1] + relative + 2), text_background)
            editable.text((margin, y + relative), line, fill=text_color, font=title_font)
            relative += text_size[1]

        return image

    def process_quiz(self, image, question, answers, font, font2):
        image = Image.open(image)
        image_size = image.size

        title_font = ImageFont.truetype(font, 30)
        title_font2 = ImageFont.truetype(font2, 30)
        editable = ImageDraw.Draw(image)

        question = self.wrap_text(question, image_size[0] - 60, title_font)
        question = "\n".join(question)

        relative = 0
        editable.text((30, 5), question.upper(), (255, 255, 255), font=title_font)

        for answer in answers:
            w_answer = "\n".join(self.wrap_text(answer, image_size[0] - 60, title_font2))
            editable.text((170, 218 + relative), w_answer, (0, 0, 0), font=title_font2)
            relative += 168

        return image

    def embed_quiz(self, quiz, image, location):
        image_size = image.size

        quiz_size = quiz.size
        quiz.thumbnail((image_size[0]*0.7, image_size[0]*0.7 * round(quiz_size[1] / quiz_size[0])), Image.ANTIALIAS)
        quiz_size = quiz.size

        margin = (image_size[0] - quiz_size[0]) // 2

        image.paste(quiz, (margin, 300), quiz)

        return image

    def process_poll(self, image, question, font):
        image = Image.open(image)
        image_size = image.size

        title_font = ImageFont.truetype(font, 30)
        editable = ImageDraw.Draw(image)

        question = self.wrap_text(question, image_size[0] - 60, title_font)
        question = "\n".join(question)

        editable.text((40, 140), question.upper(), (0, 0, 0), font=title_font)

        return image

    def embed_poll(self, quiz, image, location):
        image_size = image.size

        quiz_size = quiz.size
        quiz.thumbnail((image_size[0]*0.8, image_size[0]*0.8 * round(quiz_size[1] / quiz_size[0])), Image.ANTIALIAS)
        quiz_size = quiz.size

        margin = (image_size[0] - quiz_size[0]) // 2

        image.paste(quiz, (margin, 650), quiz)

        return image
