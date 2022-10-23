#include "generator.h"
#include "definitions.h"

#include "fvad.h"

#include <string>
#include <vector>
#include <iostream>

std::string log_level = DEFAULT_FFMPEG_LOG_LEVEL;

const char* version()
{
  return VERSION;
}

void init(const char* ffmpeg_log_level) {
  log_level = ffmpeg_log_level;
}

cut_list generate(const char *file, void (*progress)(const char*, double)) {
  // use ffmpeg to convert the file to pcm audio
  std::string command = "ffmpeg -i \"" + std::string(file) + "\" -f s16le -acodec pcm_s16le -ac 1 -ar 16000 -loglevel " + log_level + " -hide_banner -nostdin -";
  
  std::cout << "Running command: " << command << std::endl;

  FILE* pipe = popen(command.c_str(), "r");
  if (!pipe) {
    return {0, nullptr};
  }

  std::cout << "Pipe opened" << std::endl;

  // use webrtcvad to determine the speech segments
  Fvad *vad = fvad_new();
  
  fvad_set_mode(vad, 3);
  fvad_set_sample_rate(vad, 16000);

  std::vector<cut> cuts;
  cut current_cut;
  current_cut.start = 0;
  current_cut.end = 0;

  int16_t buffer[160];
  int result;

  std::cout << "Starting to read from pipe" << std::endl;

  while (true) {
    size_t read = fread(buffer, sizeof(int16_t), 160, pipe);
    if (read == 0) {
      break;
    }

    // WTF WINDOWS?!
    // ALL VALUES IN THE BUFFER ARE THE SAME?! (00000054003DD340)
    // WHY?!
    // because of the above, we can't use the buffer as a pointer to the data

    result = fvad_process(vad, buffer, 160);
    if (result == 1) {
      if (current_cut.start == 0) {
        current_cut.start = current_cut.end;
      }
    } else {
      if (current_cut.start != 0) {
        std::cout << "Found cut: " << current_cut.start << " - " << current_cut.end << std::endl;
        cuts.push_back(current_cut);
        current_cut.start = 0;
      }
    }

    current_cut.end += 0.01;
  }

  if (current_cut.start != 0) {
    std::cout << "Found cut: " << current_cut.start << " - " << current_cut.end << std::endl;
    cuts.push_back(current_cut);
  }

  std::cout << "Finished reading from pipe" << std::endl;

  fvad_free(vad);

  pclose(pipe);

  // ===========
  // FILTER CUTS
  // ===========

  std::cout << "Filtering cuts" << std::endl;

  // join cuts that are less than .2 seconds apart
  // for (int i = 0; i < cuts.size() - 1; i++) {
  //   if (cuts[i + 1].start - cuts[i].end < 0.2) {
  //     cuts[i].end = cuts[i + 1].end;
  //     cuts.erase(cuts.begin() + i + 1);
  //     i--;
  //   }
  // }
  // above code results in an access violation under windows, so the one below is way better
  
  std::cout << "Number of cuts before filtering: " << cuts.size() << std::endl;
  
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

  std::cout << "Number of cuts after filtering: " << cuts.size() << std::endl;

  // remove cuts that are shorter than .2 seconds
  cuts.erase(std::remove_if(cuts.begin(), cuts.end(), [](const cut &c) {
    return c.end - c.start < 0.2;
  }), cuts.end());

  // return the cuts
  cut* result_cuts = new cut[cuts.size()];
  for (size_t i = 0; i < cuts.size(); i++) {
    result_cuts[i] = cuts[i];
  }

  std::cout << "Assembling cut list" << std::endl;

  cut_list cutlist = { cuts.size(), result_cuts };

  std::cout << "Cuts: " << cutlist.num_cuts << std::endl;

  return cutlist;
}