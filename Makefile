.PHONY: rules test project build clean

# Compile rules/*.txt into the JSON Safari loads.
rules:
	python3 tools/build_rules.py

# Validate the compiled list and the YouTube skipper (needs node + playwright).
test: rules
	python3 tools/test_rules.py
	node tools/test_skipper.mjs

# Regenerate Feather.xcodeproj (needs: gem install xcodeproj).
project:
	ruby tools/gen_project.rb

# Build the app and both extensions with Xcode's command-line tools (macOS only).
build: rules
	xcodebuild -project Feather.xcodeproj -scheme Feather -configuration Release \
		-derivedDataPath build build

clean:
	rm -rf build
