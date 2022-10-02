FROM python:3.9-slim

ENV LECTURECUT_HOME=/LectureCut
WORKDIR ${LECTURECUT_HOME}
COPY . .

RUN apt-get update && \
    apt-get install -y gcc ffmpeg && \
    pip install -r requirements.txt

ENTRYPOINT ["python", "lecturecut.py"]
CMD ["-h"]