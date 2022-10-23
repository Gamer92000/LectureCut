cmake_minimum_required(VERSION 3.0)

set (CMAKE_CXX_STANDARD 20)

project (generator)

find_package(Threads REQUIRED)

include_directories(3rdparty/libfvad/include)
add_subdirectory(3rdparty/libfvad)

set (sources src/generator.cpp)

add_library (${PROJECT_NAME} SHARED ${sources})

find_package(OpenMP)
if(OpenMP_CXX_FOUND)
    target_link_libraries(${PROJECT_NAME} OpenMP::OpenMP_CXX)
endif()

target_link_libraries(${PROJECT_NAME} fvad)
