FROM teamacimisai/django-mssql-base-image-python3.12:latest
# FROM teamacimisai/django-mssql-base:latest

WORKDIR /app

# install dependencies
RUN pip install pip --upgrade

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# copy project
COPY . .