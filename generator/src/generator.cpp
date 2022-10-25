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
#include <cassert>
#include <thread>
#include "Windows.h"

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

result generate(
  const char *file,
  int aggressiveness,
  bool invert,
  progress_callback* progress
)
{
  // ================
  // INPUT VALIDATION
  // ================

  // check if file exists
  assert(std::filesystem::exists(file));

  // check if aggressiveness is valid
  assert(aggressiveness >= 0 && aggressiveness <= 3);

  // ==============
  // INITIALIZATION
  // ==============

  std::string id = uuid::generate_uuid_v4();
  std::filesystem::path cache_path = cache_prefix / id;
  std::filesystem::create_directories(cache_path);

  // ============
  // MEDIA -> PCM
  // ============
  std::string command = "ffmpeg -i \"" + std::string(file) + "\" -f s16le -acodec pcm_s16le -ac 1 -ar 16000 -loglevel " + log_level + " -hide_banner -nostdin -y " + (cache_path / "audio.pcm").string();

  system(command.c_str());

  #ifndef _WIN32
  std::fstream pcm_file((cache_path / "audio.pcm").string(), std::ios::in | std::ios::binary);
  #else
  // use WIN32 API to open file
  HANDLE pcm_file = CreateFile((cache_path / "audio.pcm").string().c_str(), GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
  #endif

  // =============
  // PCM -> SPEECH
  // =============

  Fvad *vad = fvad_new();
  
  fvad_set_mode(vad, aggressiveness);
  fvad_set_sample_rate(vad, 16000);

  std::vector<cut> cuts;
  cut current_cut;
  current_cut.start = 0;
  current_cut.end = 0;

  int16_t buffer[160];
  int vad_result;

  double total_video_length = 0;

  while (true) {
    #ifndef _WIN32
    pcm_file.read((char*)buffer, sizeof(int16_t) * 160);
    if (pcm_file.eof()) {
      break;
    }
    #else
    DWORD read;
    ReadFile(pcm_file, buffer, sizeof(int16_t) * 160, &read, NULL);
    if (read == 0) {
      break;
    }
    #endif
    vad_result = fvad_process(vad, buffer, 160);

    if (vad_result == 1) {
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

  #ifndef _WIN32
  pcm_file.close();
  #else
  CloseHandle(pcm_file);
  #endif

  std::error_code ec;
  std::filesystem::remove_all(cache_path, ec);
  if (ec) {
    std::cerr << "Error removing cache folder: " << ec.message() << std::endl;
  }

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

  double total_cut_length = 0;
  #pragma omp parallel for reduction(+:total_cut_length)
  for (int i = 0; i < cuts.size(); i++) {
    total_cut_length += cuts[i].end - cuts[i].start;
  }

  result result = { cutlist, {total_video_length, total_cut_length} };

  return result;
}