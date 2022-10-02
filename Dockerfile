FROM python:3.9-slim

COPY requirements.txt .

RUN apt-get update && \
    apt-get install -y gcc ffmpeg && \
    pip install --no-cache-dir -r requirements.txt

ENV LECTURECUT_HOME=/LectureCut
WORKDIR ${LECTURECUT_HOME}/src
COPY src .

ENTRYPOINT ["python", "lecturecut.py"]
CMD ["-h"]