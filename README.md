# BRilliant Web Application using the Django and React frameworks.

## Startup Guide
First, make sure all dependencies for the frontend are met by running `npm install` in the project's root. Afterwards,
build all the static files by running `npm run dev` (yes, we are currently using the development configuration). 

After these steps, you should have your staticfiles ready for serving. The django / python part also needs some
dependencies which are located in the requirements.txt file. Just install them all using `pip install -r ./requirements.txt`.

Afterwards, you can start the development server using `python manage.py runserver`.