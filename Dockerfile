# Compile render and generator (cxx)
FROM ubuntu:20.04 AS compile

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt update && apt install -y \
    build-essential \
    cmake

COPY generator /generator
COPY render /render

WORKDIR /generator
RUN cmake . && make

WORKDIR /render
RUN cmake . && make

# actual container
FROM python:3.9-slim

COPY requirements.txt .

RUN apt-get update && \
    apt-get install -y gcc ffmpeg && \
    pip install --no-cache-dir -r requirements.txt

ENV LECTURECUT_HOME=/LectureCut
WORKDIR ${LECTURECUT_HOME}/src
COPY src .

COPY --from=compile /generator/libgenerator.so ${LECTURECUT_HOME}/src/modules/generator/libdefault.so
COPY --from=compile /render/librender.so ${LECTURECUT_HOME}/src/modules/render/libdefault.so

ENTRYPOINT ["python", "lecturecut.py"]
CMD ["-h"]