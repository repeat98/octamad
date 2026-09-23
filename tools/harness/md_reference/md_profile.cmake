# Injected into the gearmulator MD fork's own configure (its CMake resolves
# paths from the top-level project, so it cannot be a subdirectory):
#
#   cmake -S vendor/gearmulator-md-mm -B out/md_reference -DCMAKE_BUILD_TYPE=Release \
#     -DDSP56K_FORCE_INTERPRETER=OFF -Dgearmulator_BUILD_JUCEPLUGIN=OFF \
#     -Dgearmulator_BUILD_JUCEPLUGIN_CLAP=OFF -Dgearmulator_SYNTH_OSIRUS=OFF \
#     -Dgearmulator_SYNTH_OSTIRUS=OFF -Dgearmulator_SYNTH_VAVRA=OFF \
#     -Dgearmulator_SYNTH_XENIA=OFF -Dgearmulator_SYNTH_NODALRED2X=OFF \
#     -Dgearmulator_SYNTH_JE8086=OFF \
#     -DCMAKE_PROJECT_gearmulator_INCLUDE=$PWD/tools/harness/md_reference/md_profile.cmake
#   cmake --build out/md_reference --target md_profile -j8
#
# The DSP emulator must carry tools/patches/gearmulator-md-exechook.patch
# (applied in vendor/gearmulator-md-mm/source/dsp56300).
add_executable(md_profile ${CMAKE_CURRENT_LIST_DIR}/md_profile.cpp)
target_link_libraries(md_profile PRIVATE mdLib)
set_target_properties(md_profile PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)

# md_replay: the voice DSP outside the Machinedrum, from an md_profile capture.
add_executable(md_replay ${CMAKE_CURRENT_LIST_DIR}/md_replay.cpp)
target_link_libraries(md_replay PRIVATE dsp56kEmu)
set_target_properties(md_replay PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)

# md_dis: every address of a snapshot's P ranges decoded, for md_relocate.py.
add_executable(md_dis ${CMAKE_CURRENT_LIST_DIR}/md_dis.cpp)
target_link_libraries(md_dis PRIVATE dsp56kEmu)
set_target_properties(md_dis PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)
