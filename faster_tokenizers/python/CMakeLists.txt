# 1. Copy the python tokenizers directory to the binary directory
add_custom_target(copy_python_tokenizers ALL
    COMMAND ${CMAKE_COMMAND} -E copy_directory ${CMAKE_SOURCE_DIR}/python ${CMAKE_BINARY_DIR}/python
    DEPENDS core_tokenizers)


# 2. Copy setup.py
add_custom_target(copy_setup ALL
    COMMAND ${CMAKE_COMMAND} -E copy ${CMAKE_SOURCE_DIR}/setup.py ${CMAKE_BINARY_DIR}/setup.py)

# 3. Copy the core_tokenizers.so libicuuc.so.70 to python tokenizers directory
set(TOKENIZER_CORE_NAME "core_tokenizers")
set(TOKENIZER_DST_DIR ${CMAKE_BINARY_DIR}/python/faster_tokenizers)

IF(WIN32)
# TODO(zhoushunjie): Need to upgrade windows
ELSE(WIN32)
add_custom_target(copy_shared_library ALL
    COMMAND ${CMAKE_COMMAND} -E copy ${CMAKE_BINARY_DIR}/faster_tokenizers/src/pybind/${TOKENIZER_CORE_NAME}.so ${TOKENIZER_DST_DIR}
    COMMAND ${CMAKE_COMMAND} -E copy ${CMAKE_BINARY_DIR}/third_party/install/icu/lib/libicuuc.so.70 ${TOKENIZER_DST_DIR}
    COMMAND ${CMAKE_COMMAND} -E copy ${CMAKE_BINARY_DIR}/third_party/install/icu/lib/libicudata.so.70 ${TOKENIZER_DST_DIR}
    DEPENDS copy_python_tokenizers)
ENDIF()
