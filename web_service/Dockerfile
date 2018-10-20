FROM python:3.7.0-slim

# set working directory
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

# add requirements (to leverage Docker cache)
ADD ./requirements.txt /usr/src/app/requirements.txt

# install requirements
RUN pip install -r requirements.txt

# add app
ADD . /usr/src/app

RUN apt-get -y upgrade
# remove uneeded packages

RUN apt-get -y --allow-remove-essential remove e2fsprogs e2fslibs gpgv apt libapt-pkg5.0

# run server
CMD python run.py
