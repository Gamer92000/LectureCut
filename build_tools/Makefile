help:                       ## This help screen
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage: make \033[3m<target>\033[0m\n\nTargets: \033[36m\033[0m\n"} /^[$$()% a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

clean:                      ## Remove all build artifacts
	rm -rf ../render/build
	rm -rf ../generator/build

render:                     ## Build the default render
	cd ../render && cmake -S . -B build
	cd ../render/build && make
	cp ../render/build/librender.* ../modules/

generator:						      ## Build the default generator
	cd ../generator && cmake -S . -B build
	cd ../generator/build && make
	cp ../generator/build/libgenerator.* ../modules/

build: render generator     ## Build the project

clean_build: clean build
