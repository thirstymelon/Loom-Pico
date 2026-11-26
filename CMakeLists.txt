cmake_minimum_required(VERSION 3.20)
project(LoomPico VERSION 1.5.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
  add_compile_options(-Wall -Wextra)
endif()

find_package(LLVM REQUIRED CONFIG)
message(STATUS "Using LLVM ${LLVM_PACKAGE_VERSION} from ${LLVM_DIR}")

add_executable(loomc-rp2040 src/main.cpp)
target_compile_definitions(loomc-rp2040 PRIVATE LOOM_TOOLCHAIN_RP2040_ONLY)
target_include_directories(loomc-rp2040 SYSTEM PRIVATE ${LLVM_INCLUDE_DIRS})
add_definitions(${LLVM_DEFINITIONS})

llvm_map_components_to_libnames(LLVM_LIBS
  Core Support Target CodeGen MC Passes
  armcodegen armasmparser armdesc arminfo
)
target_link_libraries(loomc-rp2040 PRIVATE ${LLVM_LIBS})

# Also provide `loomc` alias for direct standalone invocation
add_executable(loomc src/main.cpp)
target_compile_definitions(loomc PRIVATE LOOM_TOOLCHAIN_RP2040_ONLY)
target_include_directories(loomc SYSTEM PRIVATE ${LLVM_INCLUDE_DIRS})
target_link_libraries(loomc PRIVATE ${LLVM_LIBS})

install(TARGETS loomc-rp2040 loomc RUNTIME DESTINATION bin)
install(DIRECTORY sdk/ DESTINATION sdk)
