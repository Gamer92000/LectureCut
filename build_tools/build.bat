@REM compile ../render/CMakelists.txt
cd ..\render
cmake -DCMAKE_BUILD_TYPE=Release -B build
cmake --build build --config Release
move build\Release\render.dll ..\src\modules\render\default.dll
del /s /q build

@REM compile ../generator/CMakelists.txt
cd ..\generator
cmake -DCMAKE_BUILD_TYPE=Release -B build
cmake --build build --config Release
move build\Release\generator.dll ..\src\modules\generator\default.dll
del /s /q build