cmake_minimum_required(VERSION 3.28)
project(local_llm_openvino LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(OpenVINOGenAI REQUIRED)

add_executable(shikai src/main.cpp)
target_link_libraries(shikai PRIVATE openvino::genai openvino::runtime)
target_compile_options(shikai PRIVATE
  $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
)

install(TARGETS shikai RUNTIME DESTINATION bin)

enable_testing()
add_subdirectory(tests)
