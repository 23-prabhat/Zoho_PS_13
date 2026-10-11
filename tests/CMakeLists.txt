find_package(Python3 REQUIRED COMPONENTS Interpreter)

function(add_shikai_test test_name case_name label)
  add_test(NAME ${test_name}
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_cli.py ${case_name} $<TARGET_FILE:shikai>)
  set_tests_properties(${test_name} PROPERTIES
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR} LABELS ${label} TIMEOUT 90)
endfunction()

add_shikai_test(config_validation config unit)
add_shikai_test(missing_model_files missing_model unit)
add_shikai_test(context_limit context integration)
add_shikai_test(conversation_reset reset integration)
add_shikai_test(fresh_engine_reset_equivalence fresh_reset reliability)
add_shikai_test(metrics_reporting metrics integration)
add_shikai_test(real_model_smoke smoke integration)
add_shikai_test(complete_turn_trimming trimming integration)
add_shikai_test(conversation_continuity continuity integration)
add_shikai_test(cancellation_recovery cancellation integration)
add_shikai_test(missing_tokenizer missing_tokenizer integration)
add_shikai_test(unavailable_device unavailable_device integration)
add_shikai_test(memory_reset_cycles memory_cycles reliability)
set_tests_properties(memory_reset_cycles PROPERTIES TIMEOUT 180)

add_test(NAME network_isolated_offline
  COMMAND ${CMAKE_CURRENT_SOURCE_DIR}/offline_test.sh)
set_tests_properties(network_isolated_offline PROPERTIES
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR} LABELS offline SKIP_RETURN_CODE 77 TIMEOUT 90)
