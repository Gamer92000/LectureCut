#pragma once

#include "definitions.h"

#include <cstdio>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <array>
#include <functional>
#include <filesystem>
#include <algorithm>
#include <cmath>

std::string exec(const char* cmd) {
    std::array<char, 128> buffer;
    std::string result;
    std::unique_ptr<FILE, decltype(&pclose)> pipe(popen(cmd, "r"), pclose);
    if (!pipe) {
        throw std::runtime_error("popen() failed!");
    }
    while (fgets(buffer.data(), (int) buffer.size(), pipe.get()) != nullptr) {
        result += buffer.data();
    }
    return result;
}

std::vector<std::filesystem::directory_entry> get_dir_sorted(std::filesystem::path path) {
    std::vector<std::filesystem::directory_entry> files;
    for (const auto & entry : std::filesystem::directory_iterator(path)) {
        files.push_back(entry);
    }
    std::sort(files.begin(), files.end(), [](const auto& a, const auto& b) {
        return a.path().filename() < b.path().filename();
    });
    return files;
}

// read the progress of a ffmpeg process from stdout
// assumes that the command is executed with -progress pipe:1
void read_ffmpeg_progress(std::string cmd, double total_length, std::function<void(double)> callback) {
    std::array<char, 128> buffer;
    std::unique_ptr<FILE, decltype(&pclose)> pipe(popen(cmd.c_str(), "r"), pclose);
    if (!pipe) {
        throw std::runtime_error("popen() failed!");
    }
    double bar_total = total_length * 1000.0;
    double prev_progress = 0;
    while (fgets(buffer.data(), (int) buffer.size(), pipe.get()) != nullptr) {
        std::string line = buffer.data();
        // if the line contains "out_time_ms" it contains the progress
        if (line.find("out_time_us") != std::string::npos) {
            // get the progress value
            std::string progress = line.substr(line.find("=") + 1);
            // convert to double
            double progress_double = std::stof(progress);
            double time = std::max(progress_double, 0.0);
            // time / 1000.0 (=> seconds) / total_length (=> percentage)
            const double diff = prev_progress - (time / 1000000.0 / total_length);
            prev_progress = time / 1000000.0 / total_length;
            // call the callback
            callback(std::ceil(prev_progress * 10000.0) / 100.0);
        }
        // if the line contains "progress=end" the process is finished
        if (line.find("progress=end") != std::string::npos) {
            // call the callback with 100% progress
            callback(-1);
        }
    }
}

double get_video_length(std::filesystem::path path, std::string log_level) {
    std::string command = "ffprobe -v " + log_level + " -count_packets -select_streams v:0 -show_entries stream=nb_read_packets -of csv=p=0 \"" + path.string() + "\"";
    const int packets = std::stoi(exec(command.c_str()));
    // get frame rate
    command = "ffprobe -v " + log_level + " -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 \"" + path.string() + "\"";
    const std::string frame_rate_string = exec(command.c_str()); // has the form "30/1"
    const int frame_rate_numerator = std::stoi(frame_rate_string.substr(0, frame_rate_string.find('/')));
    const int frame_rate_denominator = std::stoi(frame_rate_string.substr(frame_rate_string.find('/') + 1));
    const double frame_rate = (double)frame_rate_numerator / (double)frame_rate_denominator;
    // calculate duration in seconds
    const double duration = packets / frame_rate;
    return duration;
}