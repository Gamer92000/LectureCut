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


## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is provided as-is and without any warranty. You are free to use it for any purpose, but I am not responsible for any damage caused by this software.

## 📝 Contributing

If you want to contribute to this project, feel free to open a pull request. I will try to review it as soon as possible.

## 🔖 TODOs

- [ ] Add NVENC support
- [ ] Fix ffmpeg Linux errors
- [ ] Improve Batch processing
- [ ] Improve argparse help
- [ ] Cleanup cache on unexpected exit
- [ ] Update README to reflect more features
- [ ] Use a more suitable cache location
