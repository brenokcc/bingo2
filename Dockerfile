FROM yml-api
WORKDIR /opt/app
EXPOSE 8000
ADD . .
ENTRYPOINT ["python", "manage.py", "startserver", "bingo"]

FROM yml-api-test as test
WORKDIR /opt/app
ADD . .
ENTRYPOINT ["python", "manage.py", "test"]
