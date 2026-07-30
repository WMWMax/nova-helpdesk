FROM python:3.7.9-alpine
WORKDIR /usr/src/nova

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apk update \
    && apk add postgresql-dev gcc python3-dev musl-dev linux-headers

RUN pip install --upgrade pip
#COPY ./req.txt .
#RUN pip install wheel
#RUN pip install gunicorn

COPY . .
RUN pip install -r req.txt
RUN pip install gunicorn

ENV HOME=/home/nova
ENV APP_HOME=$HOME/web
RUN mkdir -p $APP_HOME/staticfiles

ENTRYPOINT ["/usr/src/nova/entrypoint.sh"]