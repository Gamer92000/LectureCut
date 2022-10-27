@echo off

IF "%1"=="build" (CALL :build) ELSE ^
IF "%1"=="render" (CALL :build_render) ELSE ^
IF "%1"=="generator" (CALL :build_generator) ELSE ^
IF "%1"=="clean" (CALL :clean) ELSE ^
IF "%1"=="clean_render" (CALL :clean_render) ELSE ^
IF "%1"=="clean_generator" (CALL :clean_generator) ELSE ^
IF "%1"=="build_clean" (CALL :build_clean) ELSE (
  ECHO "Unknown command: %1"
  ECHO "Usage: build.bat [build|render|generator|clean|clean_render|clean_generator|build_clean]"
)

GOTO :eof

:build_render
  CD ..\render
  cmake -DCMAKE_BUILD_TYPE=Release -B build
  cmake --build build --config Release
  MOVE build\Release\render.dll ..\modules\render.dll
  CD ..\build_tools
  EXIT /b 0

:build_generator
  CD ..\generator
  cmake -DCMAKE_BUILD_TYPE=Release -B build
  cmake --build build --config Release
  MOVE build\Release\generator.dll ..\modules\generator.dll
  CD ..\build_tools
  EXIT /b 0

:clean_render
  CD ..\render
  DEL /s /q build
  CD ..\build_tools
  EXIT /b 0

:clean_generator
  CD ..\generator
  DEL /s /q build
  CD ..\build_tools
  EXIT /b 0

:clean
  @REM clean all build files
  CALL :clean_render
  CALL :clean_generator
  EXIT /b 0

:build
  CALL :build_render
  CALL :build_generator
  EXIT /b 0

:build_clean
  CALL :clean
  CALL :build
  EXIT /b 0