FROM python:3.8.2

ADD . /

RUN pip3 install --upgrade pip 
RUN pip3 install pipenv
RUN pipenv update

CMD [ "pipenv", "run", "python", "main.py" ]