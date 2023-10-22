FROM yml-api as web
WORKDIR /opt/app
EXPOSE 8000
RUN pip install mercadopago
RUN pip install django-redis==5.4.0
ADD . .
ENTRYPOINT ["python", "manage.py", "startserver", "bingo"]

FROM yml-api-test as test
WORKDIR /opt/app
RUN pip install mercadopago
ADD . .
ENTRYPOINT ["sh", "-c", "cp -r /opt/git .git && git pull origin $BRANCH && python manage.py test"]
