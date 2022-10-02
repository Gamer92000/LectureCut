# 🎞️ LectureCut

<div align="center">

  [![GitHub license](https://img.shields.io/github/license/Gamer92000/LectureCut)](https://github.com/Gamer92000/LectureCut/blob/main/LICENSE)
  [![GitHub commits](https://badgen.net/github/commits/Gamer92000/LectureCut/main)](https://GitHub.com/Gamer92000/LectureCut/commit/)
  [![Github stars](https://img.shields.io/github/stars/Gamer92000/LectureCut.svg)](https://GitHub.com/Gamer92000/LectureCut/stargazers/)
  <br>
  <h3>If you like this project, please consider giving it a star ⭐️!</h3>
</div>

## 📝 Description

LectureCut is a video editor for lectures. It allows you to automatically cut out parts of a video that are have no voice in it. This can cut down the time you need to watch a lecture by a lot.
LectureCut uses WebRTC to detect voice in a video. It then uses ffmpeg to cut out the parts of the video that have no voice in it. Using some advanced smart encoding techniques, LectureCut can cut down the time it takes to process a video by a lot.


## 🎃 Hacktoberfest

This project is participating in Hacktoberfest 2022. If you want to contribute, please read the [contribution guidelines](CONTRIBUTING.md) first.
Any contributions are welcome, no matter how small. If you have any questions, feel free to ask them in the [Discussions](https://github.com/Gamer92000/LectureCut/discussions) tab.
Some ideas for contributions can be found in the [issues](https://github.com/Gamer92000/LectureCut/issues) tab.

## 🚀 Usage

### 👶 Requirements

First you need to have [ffmpeg](https://ffmpeg.org/download.html) and [Python 3](https://www.python.org/downloads/) and [pip](https://pip.pypa.io/en/stable/installing/) installed.  
To install the python dependencies, simply run:
```bash
pip install -r requirements.txt
```

### 🏃 Running

To run the program, simply run:
```bash
python lecturecut.py -h
```

### 🐳 Docker
Docker is a convenient way to build and run LectureCut. Instead of manually installing and maintaining versions of ffmpeg
and various python libraries on your machine, you can utilize Docker to run LectureCut in as a container.
Moreover, this repo is expected to change at a fast pace, and so Docker is the easiest way to ensure that you're running
the most up-to-date version of LectureCut and its dependencies.

#### How it works:

After cloning this repo, you can build the image with this command:
```bash
docker build . -t lecturecut
```

Simple example: 
To run LectureCut via Docker, simply mount the file location into the container. In this example,
video.mp4 is mounted into /tmp in the container and `lecturecut` is run with the `-i` input flag pointing to this location.
```bash
docker run -it -v /path/to/video_file/on_your_machine/video.mp4:/tmp/video.mp4 lecturecut -i /tmp/video.mp4
```

Multiple directories example:
```bash
docker run -it \
  -v /path/to/input_files/:/tmp/input_files/ \
  -v /path/to/output_files/:/tmp/output_files/ \
  lecturecut -i /tmp/input_files/video_in.mp4 -o /tmp/output_files/video_out.mp4 -q 25 -a 2
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is provided as-is and without any warranty. You are free to use it for any purpose, but I am not responsible for any damage caused by this software.

## 📝 Contributing

If you want to contribute to this project, feel free to open a pull request. I will try to review it as soon as possible.
