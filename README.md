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

### 🐳 Docker
Docker is a convenient way to build and run LectureCut. Instead of manually installing and maintaining versions of ffmpeg
and various python libraries on your machine, you can utilize Docker to run LectureCut in as a container.
Moreover, this repo is expected to change at a fast pace, and so Docker is the easiest way to ensure that you're running
the most up-to-date version of LectureCut and its dependencies.

#### How it works:

Pull the LectureCut image from GitHub Container Registry.
```bash
# pull the current main
docker pull ghcr.io/gamer92000/lecturecut:main
# pull a specific release version
docker pull ghcr.io/gamer92000/lecturecut:<version>
```

Simple example: 
To run LectureCut via Docker, simply mount the file location into the container.
In this example, the current working directory is mounted into /tmp/io in the container and
`lecturecut` is run with the `-i` input flag pointing to the video in `/tmp/io` relative to the pwd.
```bash
docker run -it -v $(pwd):/tmp/io ghcr.io/gamer92000/lecturecut:main -i /tmp/io/<path to video>.mp4
```

Batch processing example:
```bash
docker run -it \
  -v /path/to/input_files/:/tmp/io/input/ \
  -v /path/to/output_files/:/tmp/io/output/ \
  ghcr.io/gamer92000/lecturecut:main -i /tmp/io/input/ -o /tmp/output -q 25 -a 2
```

### 🐍 Manual using Python

#### 👶 Requirements

First you need to have [ffmpeg](https://ffmpeg.org/download.html) and [Python 3](https://www.python.org/downloads/) and [pip](https://pip.pypa.io/en/stable/installing/) installed.  
To install the python dependencies, simply run:
```bash
pip install -r requirements.txt
```

Then you need to compile the required modules.
You need to have a C++ compiler and `cmake` and `make` installed.

##### 🐧 Linux / 🍎 macOS

Simply run:
```bash
cd build_tools
make build
```

##### 🪟 Windows

On Windows you need to have [Visual Studio](https://visualstudio.microsoft.com/) installed.  

Then in a developer command prompt run:
```bash
cd build_tools
.\build.bat
```

#### 🏃 Running

After you have installed the dependencies, you can use LectureCut by running:
```bash
python src/lecturecut.py -h
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is provided as-is and without any warranty. You are free to use it for any purpose, but I am not responsible for any damage caused by this software.

## 📝 Contributing

If you want to contribute to this project, feel free to open a pull request. I will try to review it as soon as possible.
