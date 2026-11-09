find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_executable(resource_profiler_test test_resources.cpp)
target_link_libraries(resource_profiler_test PRIVATE shikai_core)
add_test(NAME resource_profiler COMMAND resource_profiler_test)
set_tests_properties(resource_profiler PROPERTIES LABELS unit TIMEOUT 10)

function(add_shikai_test test_name case_name label)
  add_test(NAME ${test_name}
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_cli.py ${case_name} $<TARGET_FILE:shikai>)
  set_tests_properties(${test_name} PROPERTIES
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR} LABELS ${label} TIMEOUT 90)
endfunction()

add_shikai_test(config_validation config unit)
add_shikai_test(argument_validation arguments unit)
add_shikai_test(cache_option_validation cache_options unit)
add_shikai_test(missing_model_files missing_model unit)
add_shikai_test(context_limit context integration)
add_shikai_test(rejected_prompt_preserves_history rejection_history integration)
add_shikai_test(noninteractive_context_limit generate_context integration)
add_shikai_test(benchmark_jsonl_parsing jsonl integration)
add_shikai_test(single_token_metrics short_metrics integration)
add_shikai_test(resource_metrics resource_metrics integration)
add_shikai_test(kv_cache_configuration kv_config integration)
add_shikai_test(conversation_reset reset integration)
add_shikai_test(fresh_engine_reset_equivalence fresh_reset reliability)
add_shikai_test(metrics_reporting metrics integration)
add_shikai_test(real_model_smoke smoke integration)
add_shikai_test(complete_turn_trimming trimming integration)
add_shikai_test(conversation_continuity continuity integration)
add_shikai_test(cancellation_recovery cancellation integration)
add_shikai_test(streaming_generate_cancellation streaming_generate integration)
add_shikai_test(prefix_cache_reset prefix_reset integration)
add_shikai_test(conversation_benchmark conversation_benchmark integration)
add_shikai_test(cache_allocation_probe cache_probe integration)
add_shikai_test(missing_tokenizer missing_tokenizer integration)
add_shikai_test(unavailable_device unavailable_device integration)
add_shikai_test(memory_reset_cycles memory_cycles reliability)
set_tests_properties(memory_reset_cycles PROPERTIES TIMEOUT 180)

add_test(NAME preparation_and_reporting
  COMMAND ${Python3_EXECUTABLE} -m unittest discover -s ${CMAKE_CURRENT_SOURCE_DIR} -p "test_*.py")
set_tests_properties(preparation_and_reporting PROPERTIES LABELS unit TIMEOUT 30)

add_test(NAME network_denied_offline_three_turns
  COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/offline_test.py)
set_tests_properties(network_denied_offline_three_turns PROPERTIES
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR} LABELS offline SKIP_RETURN_CODE 77 TIMEOUT 90)
