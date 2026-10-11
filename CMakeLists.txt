cmake_minimum_required(VERSION 3.28)
project(local_llm_openvino LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(OpenVINOGenAI REQUIRED)

add_library(shikai_core
  src/chat_session.cpp
  src/context_policy.cpp
  src/device_probe.cpp
  src/metrics.cpp
  src/model_registry.cpp
)
target_include_directories(shikai_core PUBLIC include)
target_link_libraries(shikai_core PUBLIC openvino::genai openvino::runtime)
target_compile_options(shikai_core PRIVATE
  $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
)

add_executable(shikai src/main.cpp)
target_link_libraries(shikai PRIVATE shikai_core)
target_compile_options(shikai PRIVATE
  $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
)

install(TARGETS shikai RUNTIME DESTINATION bin)

enable_testing()
add_subdirectory(tests)
