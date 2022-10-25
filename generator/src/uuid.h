#pragma once

#include <random>
#include <sstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <cstring>

namespace uuid {
  static std::random_device              rd;
  static std::mt19937                    gen(rd());
  static std::uniform_int_distribution<> dis(0, 15);
  static std::uniform_int_distribution<> dis2(8, 11);

  const char *generate_uuid_v4() {
    std::stringstream ss;
    int i;
    ss << std::hex;
    for (i = 0; i < 8; i++) {
      ss << dis(gen);
    }
    ss << "-";
    for (i = 0; i < 4; i++) {
        ss << dis(gen);
    }
    ss << "-4";
    for (i = 0; i < 3; i++) {
        ss << dis(gen);
    }
    ss << "-";
    ss << dis2(gen);
    for (i = 0; i < 3; i++) {
        ss << dis(gen);
    }
    ss << "-";
    for (i = 0; i < 12; i++) {
        ss << dis(gen);
    };

    std::string uuid = ss.str();

    char *cstr = new char[uuid.length() + 1];
    #ifdef _WIN32
    strcpy_s(cstr, uuid.length() + 1, uuid.c_str());
    #else
    strcpy(cstr, uuid.c_str());
    #endif

    return cstr;
  }
}