cmake_minimum_required(VERSION 3.0)

set (CMAKE_CXX_STANDARD 20)

project (render)

find_package(Threads REQUIRED)

set (sources src/render.cpp)

add_library (${PROJECT_NAME} SHARED ${sources})

target_link_libraries(${PROJECT_NAME} PRIVATE Threads::Threads)

find_package(OpenMP)
if(OpenMP_CXX_FOUND)
    target_link_libraries(${PROJECT_NAME} PUBLIC OpenMP::OpenMP_CXX)
endif()