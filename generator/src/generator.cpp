// local
#include "generator.h"
#include "definitions.h"
#include "uuid.h"

// 3rdparty
#include "fvad.h"

// std
#include <string>
#include <vector>
#include <iostream>
#include <filesystem>
#include <fstream>
#include <cstdio>

std::filesystem::path tmp_path = std::filesystem::temp_directory_path();
std::filesystem::path cache_prefix = tmp_path / "LectureCut" / "Generator";

std::string log_level = DEFAULT_FFMPEG_LOG_LEVEL;

const char* version()
{
  return VERSION;
}

void init(const char* ffmpeg_log_level) {
  log_level = ffmpeg_log_level;
}

cut_list generate(
  const char *file,
  bool invert,
  progress_callback* progress
)
{
  std::string id = uuid::generate_uuid_v4();
  std::filesystem::path cache_path = cache_prefix / id;
  std::filesystem::create_directories(cache_path);
  // use ffmpeg to convert the file to pcm audio
  std::string command = "ffmpeg -i \"" + std::string(file) + "\" -f s16le -acodec pcm_s16le -ac 1 -ar 16000 -loglevel " + log_level + " -hide_banner -nostdin -y " + (cache_path / "audio.pcm").string();

  system(command.c_str());

  FILE* pcm_file;
  fopen_s(&pcm_file, (cache_path / "audio.pcm").string().c_str(), "rb");

  Fvad *vad = fvad_new();
  
  fvad_set_mode(vad, 3);
  fvad_set_sample_rate(vad, 16000);

  std::vector<cut> cuts;
  cut current_cut;
  current_cut.start = 0;
  current_cut.end = 0;

  int16_t buffer[160];
  int result;

  long total_video_length = 0;

  while (true) {
    fread(buffer, sizeof(int16_t), 160, pcm_file);
    if (feof(pcm_file)) {
      break;
    }
    result = fvad_process(vad, buffer, 160);

    if (result == 1) {
      if (current_cut.start == 0) {
        current_cut.start = current_cut.end;
      }
    } else {
      if (current_cut.start != 0) {
        cuts.push_back(current_cut);
        current_cut.start = 0;
      }
    }

    current_cut.end += 0.01;
    total_video_length += 0.01;
  }

  if (current_cut.start != 0) {
    cuts.push_back(current_cut);
  }

  fvad_free(vad);

  fclose(pcm_file);

  std::filesystem::remove_all(cache_path);

  // ======
  // INVERT
  // ======

  if (invert) {
    // create a list of cuts that are the inverse of the cuts
    std::vector<cut> inverse_cuts;
    cut inverse_cut;
    inverse_cut.start = 0;
    inverse_cut.end = 0;
    for (size_t i = 0; i < cuts.size(); i++) {
      inverse_cut.end = cuts[i].start;
      inverse_cuts.push_back(inverse_cut);
      inverse_cut.start = cuts[i].end;
    }
    inverse_cut.end = total_video_length;
    inverse_cuts.push_back(inverse_cut);

    cuts = inverse_cuts;
  }

  // ===========
  // FILTER CUTS
  // ===========
  
  // join cuts that are less than .2 seconds apart
  std::vector<cut> filtered_cuts;
  for (int i = 0; i < cuts.size(); i++) {
    if (i == cuts.size() - 1) {
      filtered_cuts.push_back(cuts[i]);
    } else if (cuts[i + 1].start - cuts[i].end < 0.2) {
      cuts[i + 1].start = cuts[i].start;
    } else {
      filtered_cuts.push_back(cuts[i]);
    }
  }
  cuts = filtered_cuts;

  // remove cuts that are shorter than .2 seconds
  cuts.erase(std::remove_if(cuts.begin(), cuts.end(), [](const cut &c) {
    return c.end - c.start < 0.2;
  }), cuts.end());

  // return the cuts
  cut* result_cuts = new cut[cuts.size()];
  for (size_t i = 0; i < cuts.size(); i++) {
    result_cuts[i] = cuts[i];
  }

  cut_list cutlist = { (long) cuts.size(), result_cuts };

  return cutlist;
}