#!make

all: build

build: ./gradlew build

changelog:
	github_changelog_generator -u henriquesebastiao -p downtify-android -o CHANGELOG --no-verbose
	@echo "Changelog generated at CHANGELOG"

%:
	@:

.PHONY: all build changelog
