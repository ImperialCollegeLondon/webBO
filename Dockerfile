FROM continuumio/miniconda3

RUN conda update conda
COPY environment.yml .
RUN conda env create -f environment.yml

COPY . /usr/src/app

WORKDIR /usr/src/app

CMD /opt/conda/envs/suprashare/bin/gunicorn main:app -b :8050
EXPOSE 8050