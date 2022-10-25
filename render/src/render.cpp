// local
#include "render.h"
#include "helper.h"
#include "definitions.h"
#include "uuid.h"

// std
#include <map>
#include <mutex>
#include <filesystem>
#include <string>
#include <iostream>
#include <sstream>
#include <thread>
#include <cstring>
#include <fstream>
#include <omp.h>
#include <system_error>
#include <cassert>


// make sure render is only started after prepare is done for a given file
std::mutex process_map_mutex;
std::map<std::string, std::mutex> processes;
std::mutex& GetMutexForProcess(const std::string process)
{
  std::lock_guard lock(process_map_mutex);
  // (creates a new mutex if it doesn't exist yet)
  std::mutex &mutex = processes[process];
  return mutex;
}

std::map<std::string, std::vector<std::tuple<double, double>>> instance_segment_data;

std::filesystem::path tmp_path = std::filesystem::temp_directory_path();
std::filesystem::path cache_prefix = tmp_path / "LectureCut" / "Render";

std::string log_level = DEFAULT_FFMPEG_LOG_LEVEL;

const char* version()
{
  return VERSION;
}

void init(const char* ffmpeg_log_level)
{
  log_level = ffmpeg_log_level;
}

void internal_prepare(
  const std::string file,
  const std::string process,
  progress_callback *progress
)
{
  // ==============
  // INITIALIZATION
  // ==============

  // lock the mutex for this process
  std::lock_guard lock(GetMutexForProcess(process));

  // create the instances cache folder
  std::filesystem::path segment_path = cache_prefix / process / "segments";
  std::filesystem::create_directories(segment_path);

  // ============
  // SEGMENTATION
  // ============

  std::string command = "ffmpeg -i \"" + std::string(file) + "\" -c copy -f segment -reset_timestamps 1 -loglevel " + log_level + " -hide_banner -nostdin \"" + (segment_path / "out%05d.ts").string() + "\"";

  // execute the command
  exec(command.c_str());
  
  // get a list of all directory_entries (segments)
  std::vector<std::filesystem::directory_entry> segments = get_dir_sorted(segment_path);

  // =================
  // SEGMENT ANALZYSIS
  // =================

  // initialize the vector for the instance data with the correct size
  std::vector<double> segment_length;
  segment_length.resize(segments.size());
  
  const double progress_delta = 100.0 / segments.size();

  #pragma omp parallel for num_threads(omp_get_num_procs() / 4)
  for (int i = 0; i < segments.size(); i++)
  {
    auto &entry = segments[i];
    // get frame count
    std::string command = "ffprobe -v " + log_level + " -count_packets -select_streams v:0 -show_entries stream=nb_read_packets -of csv=p=0 \"" + entry.path().string() + "\"";
    const int packets = std::stoi(exec(command.c_str()));
    // get frame rate
    command = "ffprobe -v " + log_level + " -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 \"" + entry.path().string() + "\"";
    const std::string frame_rate_string = exec(command.c_str()); // has the form "30/1"
    const int frame_rate_numerator = std::stoi(frame_rate_string.substr(0, frame_rate_string.find('/')));
    const int frame_rate_denominator = std::stoi(frame_rate_string.substr(frame_rate_string.find('/') + 1));
    const double frame_rate = (double)frame_rate_numerator / (double)frame_rate_denominator;
    // calculate duration
    const double duration = packets / frame_rate;
    // add to segment_length
    segment_length[i] = duration;
    progress("Analysing", progress_delta);
  }
  // Set progress to 100%
  progress("Analysing", -1);

  // ================
  // DURATION -> TIME
  // ================

  std::vector<std::tuple<double, double>> instance_data;
  double start = 0;
  for (const auto &length : segment_length)
  {
    instance_data.push_back(std::make_tuple(start, start + length));
    start += length;
  }
  instance_segment_data[process] = instance_data;

  // unlock the mutex for this process (automatically done by the destructor)
}

const char *prepare(
  const char *file,
  progress_callback *progress
)
{
  // ================
  // INPUT VALIDATION
  // ================

  // check if file exists
  assert(std::filesystem::exists(file));

  // ==============
  // INITIALIZATION
  // ==============

  // generate a random ID that will be used to identify the render
  // this is used to prevent the render from being overwritten by another
  // render with the same name
  const char *id = uuid::generate_uuid_v4();

  // make sure file is not destroyed before the thread is done
  std::string file_copy = std::string(file);

  // start a thread that will load the file and segment it
  std::thread t(internal_prepare, file_copy, std::string(id), progress);
  t.detach();

  return id;
}

void render(
  const char *process,
  const char *output,
  cut_list cuts,
  int quality,
  progress_callback *progress
)
{
  // ================
  // INPUT VALIDATION
  // ================

  // check that a mutex for this process exists
  assert(processes.find(process) != processes.end());

  // check if output file exists (should not)
  assert(!std::filesystem::exists(output));

  // check that the quality is in the correct range (quality is a number between 0 and 51)
  assert(quality >= 0 && quality <= 51);

  // ==============
  // INITIALIZATION
  // ==============

  // wait until the mutex for this process is unlocked
  std::lock_guard lock(GetMutexForProcess(process));

  std::filesystem::path cache_path = cache_prefix / process;
  std::filesystem::path segment_path = cache_path / "segments";
  std::filesystem::path cut_path = cache_path / "cuts";
  std::filesystem::create_directories(cut_path);

  // get a list of all directory_entries (segments)
  std::vector<std::filesystem::directory_entry> segments = get_dir_sorted(segment_path);

  const double progress_delta = 100.0 / segments.size();

  // ===========
  // TRANSCODING
  // ===========

  #pragma omp parallel for num_threads(omp_get_num_procs() / 4)
  for (int i = 0; i < segments.size(); i++)
  {
    auto &entry = segments[i];
    // get the start and duration of the segment
    const double start = std::get<0>(instance_segment_data[process][i]);
    const double end = std::get<1>(instance_segment_data[process][i]);
    
    // find id of first cut ending after segment start
    int first_cut_id = -1;
    std::tuple<double, double> first_cut;
    for (int j = 0; j < cuts.num_cuts; j++)
    {
      if (cuts.cuts[j].end > start)
      {
        first_cut_id = j;
        first_cut = std::make_tuple(cuts.cuts[j].start, cuts.cuts[j].end);
        break;
      }
    }

    // skip segment if it ends before the current cut starts
    if (first_cut_id == -1 || end <= std::get<0>(first_cut))
    {
      progress("Transcoding", progress_delta);
      continue;
    }

    // if completely enclosed by a cut, move
    if (start >= std::get<0>(first_cut) && end <= std::get<1>(first_cut))
    {
      std::filesystem::rename(entry.path(), cut_path / entry.path().filename());
      progress("Transcoding", progress_delta);
      continue;
    }

    std::vector<cut> cuts_in_segment;
    // find all cuts that start before segment end
    // only look at cuts with an id >= first_cut_id
    for (int j = first_cut_id; j < cuts.num_cuts && cuts.cuts[j].start < end; j++)
    {
      cuts_in_segment.push_back(cuts.cuts[j]);
    }

    // generate a keep list
    std::vector<cut> keep_list;
    for (auto &cut : cuts_in_segment)
    {
      double keep_start = std::max(start, cut.start);
      double keep_end = std::min(end, cut.end);
      keep_list.push_back({keep_start, keep_end});
    }

    // filter keep list to remove segments that are too short
    keep_list.erase(std::remove_if(keep_list.begin(), keep_list.end(), [](auto &cut){
      return cut.end - cut.start <= 0.1;
    }), keep_list.end());

    // convert keep list from global time to segment time
    for (auto &cut : keep_list)
    {
      cut.start -= start;
      cut.end -= start;
    }

    for (int j = 0; j < keep_list.size(); j++)
    {
      auto &cut = keep_list[j];
      std::string command = "ffmpeg -i \"" + entry.path().string() + "\" -f mpegts";
      std::ostringstream f_name;
      f_name << "out" << std::setfill('0') << std::setw(5) << i << "_" << std::setfill('0') << std::setw(3) << j << ".ts";
      std::string file_name = f_name.str();
      if (cut.start == 0) {
        command += " -to " + std::to_string(cut.end) + " -c copy \"" + (cut_path / file_name).string() + "\"";
      }
      else {
        command += " -ss " + std::to_string(cut.start) + " -to " + std::to_string(cut.end) + " -acodec copy -vcodec libx264 -preset fast -crf " + std::to_string(quality) + " -reset_timestamps 1 -force_key_frames 0 \"" + (cut_path / file_name).string() + "\"";
      }
      command += " -loglevel " + log_level + " -hide_banner -nostdin";

      exec(command.c_str());
    }
    progress("Transcoding", progress_delta);
  }
  // Set the progress to 100%
  progress("Transcoding", -1);

  // ===========
  // CONCATENATE
  // ===========

  std::vector<std::filesystem::directory_entry> cut_files = get_dir_sorted(cut_path);

  // create concat file in cache
  std::ofstream concat_file((cache_path / "concat.txt").string());
  for (const auto &entry : cut_files)
  {
    concat_file << "file 'cuts/" << entry.path().filename().string() << "'" << std::endl;
  }
  concat_file.close();

  // concatenate all segments in the cut folder
  std::string command = "ffmpeg -f concat -safe 0 -i " + (cache_path / "concat.txt").string() + " -c copy \"" + output + "\" -loglevel " + log_level + " -hide_banner -nostdin";

  exec(command.c_str());

  // =======
  // CLEANUP
  // =======

  // remove the cache folder for this process
  std::error_code ec;
  std::filesystem::remove_all(cache_path, ec);

  if (ec)
  {
    std::cerr << "Error removing cache folder: " << ec.message() << std::endl;
  }
}